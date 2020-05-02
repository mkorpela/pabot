# Pabot

[In English](README.md)
[中文版](README_zh.md)

[![Version](https://img.shields.io/pypi/v/robotframework-pabot.svg)](https://pypi.python.org/pypi/robotframework-pabot)
[![Downloads](http://pepy.tech/badge/robotframework-pabot)](http://pepy.tech/project/robotframework-pabot)
[![Build Status](https://travis-ci.org/mkorpela/pabot.svg?branch=master)](https://travis-ci.org/mkorpela/pabot)
[![Build status](https://ci.appveyor.com/api/projects/status/5g52rkflbtfw2anb/branch/master?svg=true)](https://ci.appveyor.com/project/mkorpela/pabot/branch/master)


<img src="https://raw.githubusercontent.com/mkorpela/pabot/master/pabot.png" width="100">

----

Параллельный исполнитель для тестов [Robot Framework](http://www.robotframework.org). С Pabot вы можете разделить одно выполнение на несколько и сэкономить время выполнения теста.

## Монтаж:

From PyPi:

     pip install -U robotframework-pabot

OR clone this repository and run:

     setup.py  install

## Вещи, которые вы должны знать

   - По умолчанию Pabot будет отделять выполнение теста от файлов набора. Для разделения уровня теста используйте флаг ```--testlevelsplit```.
   - В общем случае вы не можете рассчитывать на тесты, которые не предназначены для параллельного выполнения, чтобы работать "из коробки" при параллельном выполнении. Например, если тесты манипулируют или используют одни и те же данные, вы можете столкнуться с проблемами (один набор тестов входит в систему, а другой - в тот же сеанс и т. Д.). PabotLib может помочь вам решить эти проблемы параллелизма.

## Вклад в проект

Есть несколько способов улучшить этот инструмент:

   - Сообщите о проблеме или идее улучшения [средство отслеживания проблем](https://github.com/mkorpela/pabot/issues)
   - Внесите свой вклад, запрограммировав и сделав запрос на извлечение (самый простой способ - это решить проблему с помощью системы отслеживания проблем)

## Параметры командной строки

    pabot [--verbose|--testlevelsplit|--command .. --end-command|
           --processes num|--pabotlib|--pabotlibhost host|--pabotlibport port|
           --artifacts extensions|--artifactsinsubfolders|
           --resourcefile file|--argumentfile[num] file|--suitesfrom file] 
          [robot options] [path ...]


Поддерживает все параметры командной строки Robot Framework, а также следующие параметры (они должны быть перед обычными параметрами RF):

--verbose     
  больше выхода из параллельного исполнения

--testlevelsplit          
  Разделить выполнение на уровне теста вместо уровня набора по умолчанию.
  Если .pabotsuitenames содержит и тесты, и наборы, то это
  повлияет только на новые сюиты и разделит только их.
  Оставив этот флаг, когда и наборы и тесты в
  Файл .pabotsuitenames также влияет только на новые
  добавьте их как файлы набора.

--command [ACTUAL COMMANDS TO START ROBOT EXECUTOR] --end-command    
  Скрипт Robot Framework для ситуаций, когда Pybot не используется напрямую.

--processes   [NUMBER OF PROCESSES]          
  Сколько параллельных исполнителей использовать (по умолчанию максимум 2 и количество процессоров).

--pabotlib          
  Запустите PabotLib удаленный сервер. Это позволяет блокировать и распределять ресурсы между параллельными выполнениями теста.

--pabotlibhost   [HOSTNAME]          
  Имя хоста удаленного сервера PabotLib (по умолчанию 127.0.0.1)
  Если используется с параметром --pabotlib, изменит адрес прослушивания хоста созданного удаленного сервера (см. Https://github.com/robotframework/PythonRemoteServer)
  Если используется без параметра --pabotlib, подключится к уже запущенному экземпляру удаленного сервера PabotLib на данном хосте. Удаленный сервер также может быть запущен и выполнен отдельно от экземпляров pabot:
  
      python -m pabot.PabotLib <path_to_resourcefile> <host> <port>
      python -m pabot.PabotLib resource.txt 192.168.1.123 8271
  
  Это позволяет совместно использовать ресурс с несколькими экземплярами Robot Framework.

--pabotlibport   [PORT]          
  Номер порта удаленного сервера PabotLib (по умолчанию 8270)
  Смотрите --pabotlibhost для получения дополнительной информации

--resourcefile   [FILEPATH]          
  Индикатор для файла, который может содержать общие переменные для распределения ресурсов. Это нужно использовать вместе с опцией pabotlib. Синтаксис файла ресурсов такой же, как и у файлов Windows ini. Где раздел является общим набором переменных.

--artifacts [FILE EXTENSIONS]   
  Список из разрешений файлов через запятую.    
  Файлы с такими разрешениями (скриншоты, видео и т.д. )будут скопированы из отдельных выходных папок в итоговую выходную директорию.
  Если в RF логах есть ссылки на эти файлы, то пут будут скорректирован (поддерживаются только относительные пути).   
  Значение по умолчанию - `png`.    
  Пример:

     --artifacts png,mp4,txt

--artifactsinsubfolders   
  Будут скопированы файлы не только из корня выходной директории, но из ее подпапок.

--argumentfile[INTEGER]   [FILEPATH]          
  Запустите одни и те же наборы с несколькими параметрами [аргумент-файл] (http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#argument-files).
  For example:

     --argumentfile1 arg1.txt --argumentfile2 arg2.txt

--suitesfrom   [FILEPATH TO OUTPUTXML]          
  При желании читать наборы из файла output.xml. Неудачные наборы будут работать
  первые и более продолжительные из них будут выполнены перед более короткими.

Example usages:

     pabot test_directory
     pabot --exclude FOO directory_to_tests
     pabot --command java -jar robotframework.jar --end-command --include SMOKE tests
     pabot --processes 10 tests
     pabot --pabotlibhost 192.168.1.123 --pabotlibport 8271 --processes 10 tests
     pabot --pabotlib --pabotlibhost 192.168.1.111 --pabotlibport 8272 --processes 10 tests
     pabot --artifacts png,mp4,txt --artifactsinsubfolders directory_to_tests

### PabotLib

pabot.PabotLib предоставляет ключевые слова, которые помогут коммуникации и обмену данными между процессами исполнителя.
Это может быть полезно, когда вы должны убедиться, что только один из процессов использует какой-то фрагмент данных или одновременно работает с какой-либо частью тестируемой системы.

Docs are located at https://mkorpela.github.io/PabotLib.html

### PabotLib example:

test.robot

      *** Settings ***
      Library    pabot.PabotLib
      
      *** Test Case ***
      Testing PabotLib
        Acquire Lock   MyLock
        Log   This part is critical section
        Release Lock   MyLock
        ${valuesetname}=    Acquire Value Set  admin-server
        ${host}=   Get Value From Set   host
        ${username}=     Get Value From Set   username
        ${password}=     Get Value From Set   password
        Log   Do something with the values (for example access host with username and password)
        Release Value Set
        Log   After value set release others can obtain the variable values

valueset.dat

      [Server1]
      tags=admin-server
      HOST=123.123.123.123
      USERNAME=user1
      PASSWORD=password1
      
      [Server2]
      tags=server
      HOST=121.121.121.121
      USERNAME=user2
      PASSWORD=password2

      [Server2]
      tags=admin-server
      HOST=222.222.222.222
      USERNAME=user3
      PASSWORD=password4


pabot call

      pabot --pabotlib --resourcefile valueset.dat test.robot

### Контроль порядка выполнения и уровня параллелизма

Файл .pabotsuitenames содержит список пакетов, которые будут выполнены.
Файл создается во время выполнения pabot, если его там еще нет.
Файл представляет собой кэш, который использует pabot при повторном выполнении тех же тестов для ускорения обработки.
Этот файл может быть частично отредактирован вручную.
Первые 4 строки содержат информацию, которую не нужно редактировать - pabot будет редактировать ее, когда что-то изменится.
После этого идут названия люксов. 

Есть три возможности повлиять на исполнение:

  * Порядок номеров может быть изменен.
  * Если каталог (или структура каталогов) должен выполняться последовательно, добавьте имя набора каталогов в строку.
  * Вы можете добавить строку с текстом `# WAIT`, чтобы заставить исполнителя ждать, пока все предыдущие наборы не будут выполнены.

### Глобальные переменные

Pabot вставит следующие глобальные переменные в пространство имен Robot Framework. Они здесь, чтобы включить функциональность PabotLib и для пользовательских слушателей и т. Д., Чтобы получить некоторую информацию об общем выполнении Pabot.

      PABOTLIBURI - содержит URI для работающего сервера PabotLib
      PABOTEXECUTIONPOOLID - он содержит идентификатор пула (целое число) для текущего исполнителя Robot Framework. Это полезно, например, при визуализации потока выполнения от вашего собственного слушателя.
 
