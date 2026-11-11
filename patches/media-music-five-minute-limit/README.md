# Set the YuE2 maximum to five minutes

The public music API and duration controls use the same 300-second limit. The API translates it to 7,500 semantic tokens and returns HTTP 422 for larger budgets. YuE2 may finish before the cap.

Публичный API и настройки YuE2 используют предел 300 секунд или 7 500 семантических токенов. Запросы выше предела получают HTTP 422. YuE2 может закончить песню раньше.
