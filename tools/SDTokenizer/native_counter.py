"""Experimental exact-source SD-Qwen counter; no runtime guard or inference.

Uses only the existing original Native EXE's merge resource. No HF tokenizer,
replacement vocabulary, model weights, Native DLL loading, or network calls.
Parity must be reviewed before connecting this prototype to the public API.
"""
from pathlib import Path
from functools import lru_cache
import argparse
import hashlib
import json
import math
import re
import struct
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'deps'))
import regex


def f32(value):
    try:return struct.unpack('f',struct.pack('f',value))[0]
    except OverflowError:return math.copysign(math.inf,value)


def parse_attention(text):
    """Pinned util.cpp behavior, including its existing escaping/weight quirks."""
    result=[];rounds=[];squares=[]
    pattern=re.compile(r'\\\(|\\\)|\\\[|\\\]|\\\\|\\|\(|\[|\)|\]|\bBREAK\b|[^\\()\[\]:B]{1,1024}|:|\bB',re.ASCII)
    breaks=re.compile(r'\s*\bBREAK\b\s*',re.ASCII)
    def multiply(start,value):
        for index in range(start,len(result)):
            result[index][1]=f32(result[index][1]*value)
    remaining=text
    while (match:=pattern.search(remaining)) is not None:
        token=match.group();suffix=remaining[match.end():]
        if token==':':
            weight=re.match(r'([+-]?[0-9.]*)\)',suffix,re.ASCII)
            if weight:
                try:value=f32(float(weight.group(1)))
                except ValueError:value=math.nan
                if math.isfinite(value):
                    if rounds:multiply(rounds.pop(),value)
                    remaining=suffix[weight.end():]
                    continue
        if token=='(':rounds.append(len(result))
        elif token=='[':squares.append(len(result))
        elif token==')' and rounds:multiply(rounds.pop(),f32(1.1))
        elif token==']' and squares:multiply(squares.pop(),f32(1/f32(1.1)))
        elif token=='\\(':result.append([token[1:],f32(1)])
        elif breaks.search(token):result.append(['BREAK',f32(-1)])
        else:result.append([token,f32(1)])
        remaining=suffix
    for start in rounds:multiply(start,f32(1.1))
    for start in squares:multiply(start,f32(1/f32(1.1)))
    if not result:result=[['',f32(1)]]
    merged=[]
    for text,weight in result:
        if merged and merged[-1][1]==weight:merged[-1][0]+=text
        else:merged.append([text,weight])
    return merged


class NativeQwenCounter:
    experimental=True
    def __init__(self):
        self.spec=json.loads((HERE/'native-qwen-spec.json').read_text(encoding='utf-8'))
        provenance=json.loads((HERE/'native-resource-provenance.json').read_text(encoding='utf-8'))
        path=HERE/'qwen2-merges.native.txt'
        if hashlib.sha256(path.read_bytes()).hexdigest()!=provenance['resource_sha256']:
            raise ValueError('Existing Native merge resource SHA mismatch.')
        # Native Windows text-resource loading and actual token parity determine
        # this newline convention; raw resource provenance retains all CRLF bytes.
        text=path.read_text(encoding='utf-8')
        rows=text.split('\n')
        if rows[-1]=='':rows.pop()
        self.merges=[]
        for row in rows:
            left,separator,right=row.partition(' ')
            if not separator:raise ValueError('Malformed Native merge row.')
            self.merges.append((left,right))
        visible=list(range(ord('!'),ord('~')+1))+list(range(161,173))+list(range(174,256))
        self.byte_encoder={value:chr(value) for value in visible}
        extra=0
        for value in range(256):
            if value not in self.byte_encoder:
                self.byte_encoder[value]=chr(256+extra);extra+=1
        ordered=[self.byte_encoder[value] for value in visible]+[self.byte_encoder[value] for value in range(256) if value not in visible]
        tokens=ordered+[a+b for a,b in self.merges]+self.spec['special_tokens']
        self.encoder={token:index for index,token in enumerate(tokens)}
        self.ranks={pair:index for index,pair in enumerate(self.merges)}
        self.specials=set(self.spec['special_tokens'])
        self.special_pattern=regex.compile('('+'|'.join(regex.escape(t) for t in self.spec['special_tokens'])+')',regex.VERSION0)
        self.pattern=regex.compile(self.spec['pattern'],regex.VERSION0)
        self.unknown=self.spec['unknown_token_id']

    @lru_cache(maxsize=16384)
    def bpe(self,token):
        word=list(token)
        while len(word)>1:
            pairs=set(zip(word,word[1:]))
            valid=[pair for pair in pairs if pair in self.ranks]
            if not valid:break
            first,second=min(valid,key=self.ranks.__getitem__)
            merged=[];index=0
            while index<len(word):
                if index+1<len(word) and word[index]==first and word[index+1]==second:
                    merged.append(first+second);index+=2
                else:merged.append(word[index]);index+=1
            word=merged
        return tuple(word)

    def encode_piece(self,text):
        if not isinstance(text,str):raise TypeError('Tokenization input must be a string.')
        strings=[]
        for piece in self.special_pattern.split(text):
            if not piece:continue
            if piece in self.specials:strings.append(piece);continue
            for token in self.pattern.findall(piece):
                encoded=''.join(self.byte_encoder[value] for value in token.encode('utf-8'))
                strings.extend(self.bpe(encoded))
        return dict(ids=[self.encoder.get(token,self.unknown) for token in strings],strings=strings,count=len(strings))

    def native_request(self,payload,trigger=None):
        """Count final positive text exactly as this static-LoRA Native path.

        trigger=None expects an already-prefixed proxy/benchmark payload. Passing
        physioshade optionally reproduces the existing proxy's prefix/dedup rule.
        Runtime LoRA tags are deliberately unsupported until their removal path
        is separately reproduced. No trimming beyond Native's existing3000bytes.
        """
        if not isinstance(payload,dict):raise TypeError('Payload must be an object.')
        prompt=payload.get('prompt','high quality');forced=payload.get('add_sd_prompt','')
        if not isinstance(prompt,str) or not isinstance(forced,str):raise TypeError('Native prompt and add_sd_prompt must be strings.')
        if '<lora:' in (prompt+forced).lower():raise ValueError('Runtime LoRA directives are not covered by this prototype.')
        if trigger and not re.search(r'(?<!\w)'+re.escape(trigger)+r'(?!\w)',prompt,re.IGNORECASE):
            prompt=trigger+(', '+prompt if prompt else '')
        native_body=', '.join([prompt.encode('utf-8')[:3000].decode('utf-8',errors='ignore'),forced])
        pieces=[['<|im_start|>user\n',f32(1)],*parse_attention(native_body),['<|im_end|>\n<|im_start|>assistant\n',f32(1)]]
        output=[dict(text=text,weight=weight,**self.encode_piece(text)) for text,weight in pieces]
        count=sum(item['count'] for item in output)
        width,height=payload.get('width',800),payload.get('height',1200)
        if any(type(value)is not int or value<=0 or value%16 for value in (width,height)):
            raise ValueError('An explicit aligned16 image geometry is required.')
        image_tokens=(width//16)*(height//16)
        padded_image=(image_tokens+31)//32*32;padded_text=(count+31)//32*32
        score=4*30*(padded_image+padded_text)**2
        return dict(status='experimental_not_runtime_guard',native_positive_body=native_body,
            pieces=output,token_ids=[token for item in output for token in item['ids']],
            caption_tokens=count,padded_caption_tokens=padded_text,image_tokens=image_tokens,
            padded_image_tokens=padded_image,estimated_F32_attention_score_bytes=score,
            below_observed_2GiB_score_tensor_limit=score<=2147483648,
            limitation='Score-tensor estimate only, not total VRAM or universal model compatibility. Other paths/ref_images/negativeCFG are not covered.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload',type=Path,required=True)
    parser.add_argument('--trigger',default=None)
    args=parser.parse_args()
    value=json.loads(args.payload.read_text(encoding='utf-8-sig'))
    payload=value.get('payload',value)
    print(json.dumps(NativeQwenCounter().native_request(payload,args.trigger),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
