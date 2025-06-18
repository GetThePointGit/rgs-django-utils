
## Logging in de taken van de SPOC

Gebruik de volgende functies bij het loggen:
- `set_run(name: str)` en `finish_run()` voor een gehele run van meerdere taken. Deze run komt in LogRun in de 
  database en admin. De logging wordt gelinkt aan de LogRun.
- Individuele taken worden gelogd met `set_task(name: str, log_timing: bool = True)` en `finish_task()`. De taak wordt
  opgenomen als kolom bij de logging en gebruikt als kopje in de admin bij de logs. Van de taken wordt automatisch
  de tijd gelogd (naar het kanaal 'task.performance') bij finish_task() als `log_timing=True`. Ook worden aantallen gelogd indien aanwezig.
- met de `log_counter(name: str, number: int = 1)` kunnen aantallen worden gelogd. Deze worden opgeteld bij finish_task().
  en dan gelogd naar het kanaal ('task.performance')
- Performance van subtaken kan worden gelogd met 'timer = SubTimer(name: str)' en dan 'timer.finish()' aan het eind,
  waarna de tijd wordt gelogd naar het kanaal 'task.performance.sub'.
- Verder kunnen nog extra gegevens worden meegegeven naar de database, onder andere door log.info('iets', extra={'key': 'value'}).
  Deze worden opgenomen in de kolom 'extra' in de database of voor meerdere loggings door de functie `set_extra_info(info: dict)` en daarna
  `clear_extra_info()`.

Zie voorbeelden van het gebruik in [test_db_logging.py](..%2F..%2Ftests%2Ftest_db_logging.py) of in de taken zelf.

Speciale loggers om te gebruiken:
- `data_log = get_data_logger(__name__)` voor logging van meldingen over data. Deze worden apart gelabeld in de
  database, kunnen apart worden bekeken in de admin en worden apart gebruikt voor bepalen van de status van een taak.
- `task_console_info` is een logger die alleen naar de console logt. Gebruik deze bij commando's in plaats van 
  `self.stdout.write()` (geeft soms problemen als deze wordt aangeroepen vanuit de admin/ webserver). Meldingen
  over het starten en eindigen van runs, taken en subtaken worden automatisch naar de console gelogd.


## Logging bekijken en opruimen:

In de admin kan de logging per LogRun worden bekeken of gewoon in 'Log' voor alle logging (ook niet gekoppeld aan een run).
Bij Log wordt ook getoond vanuit welk stuk code (filename en regel) er gelogd wordt.

Bij Logrun kan logging worden opgeruimd via de admin door de actie 'cleanup_old_logs'. Bij een selectie doet hij dat voor de geselecteerde runs.
Als er geen selectie is gemaakt worden alle logging ouder dan dan 30 dagen verwijderd (behalve die over performance) en
alle logRuns ouder dan een jaar.

logs verwijderen kan ook met het volgende management command:
```bash
python manage.py cleanup_old_logs --period_days_logs 30 --period_days_logruns 365
```



## Example 

```python
import logging
from spoc_hhnk.utils.logging import set_run, finish_run, set_task, finish_task, log_counter, SubTimer
from spoc_hhnk.utils.logging.loggers import task_console_info, get_data_logger

# preferably, also send all logs related to data to 'data.....'
log = logging.getLogger(__name__)
# aparte logger voor data (met andere status en afhandeling)
data_log = get_data_logger(__name__)


def run_task():
    set_run('test_run')
    # set run context and log to console start of run
    set_task('task1')
    # set task context, start timers and log to console start of task1
    task_console_info('extra informatie alleen voor console.')
    # log to console only
    
    timer = SubTimer('subtask1')
    for i in range(8):
        log_counter('counter1')
        log_counter('counter2', 2)
    
    data_log.info('some data', extra={'key': 'value'})
    # logs directly to database with extra info
        
    timer.finish()
    # this logs the time of subtask1: "sub subtask1: duration: 0.050s, process_duration: 0.001s"
    
    # of gebruik de subtimer zo:
    with SubTimer('subtask2'):
        for i in range(8):
            log_counter('counter1')
            log_counter('counter2', 2)
    # this logs the time of subtask2: "sub subtask2: duration: 0.050s, process_duration: 0.001s"s
    
    finish_task()
    # this logs the time of task1: "taak task1: duration: 0.050s, process_duration: 0.001s"
    # and the counter information:
    # "* Task summary task1"
    # "  - counter1: 8"
    # "  - counter2: 16"
    
    finish_run()
    # this writes the time of the run and status to the database.

if __name__ == '__main__':
    run_task()
```







