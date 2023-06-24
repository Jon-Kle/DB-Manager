# DB-Manager

[english version](/README.md)

Dieses Programm sammelt regelmäßig die Wetterdaten der [weatherlink Website](weatherlink.com) von Davis instruments, und speichert sie in einer MySQL Datenbank.

Der Code für die Website zur Anzeige der Daten wird in der Zukunft ebenfalls auf Github gestellt werden.

Dies ist ein Schulprojekt. Wenn du einen Beitrag leisten willst, bitte lies die Datei [CONTRIBUTING.md](CONTRIBUTING.md).

## Index:
- [Über das Projekt](#about-this-project)
- [Setup](#setup)
    - [Docker](#docker)
    - [Docker-Container für MySQL](#docker-container-für-mysql)
    - [Docker-Container für phpMyAdmin](#docker-container-für-phpmyadmin)
    - [Docker-Networking](#docker-networking)
    - [Einrichten der Datenbank](#einrichten-der-datenbank)
    - [Docker-Container für die Website](#docker-container-für-die-website)
    - [git-secret](#git-secret)
- Bedienung
- Entwicklung

## Über das Projekt

Dieses Projekt begann 2015 als eine Vertiefungsarbeit von einem ehemaligen Schüler. Er erstellte die Website und ein C++-Programm als Erweiterung für die Wetterüberwachungssoftware, die mit der Wetterstation kam Er hatte vor, das gesamte Setup lokal in der Schule laufen zu lassen, kam aber nie dazu, es aufzubauen.  
Einige Jahre später 2022 begann ich an dem Code zu Arbeiten, aber ich merkte, dass der C++-Code fehlte. Also ersetzte ich diesen Teil und beschloss, das Setup zu ändern und die Daten von den Servern von Davis Instruments über die API abzurufen. Zum einen, weil die mitgelieferte Software 24/7 auf einem Windows-PC hätte laufen müssen, zum anderen, weil diese Software uralt war. Der DB-Manager ist dieser Ersatz.

Ich persönlich hoffe, dass andere Schüler diese Arbeit weiterführen werden. Der **DB-Manager** ist soweit fertig, aber zum Beispiel eine automatische Datenbankvervollständigung nach einem Ausfall könnte noch hinzugefügt werden.  
Die **Website** hingegen kann verbessert und erweitert werden um Wetterdaten auf mehr Varianten anzuzeigen. Die einzige Bedingung ist, dass *das grundlegende Design der Website gleich bleibt.*  
Der Schüler, der sie ursprünglich entworfen und programmiert hat, sollte seine Arbeit wiedererkennen können.

## Setup

Das Setup hat zum Ziel, die Daten von der Wetterstation an der Schule auf die Website zu bringen. Um das zu erreichen, ist eine Kette von Elementen nötig:

Verbunden mit der **Wetterstation** ist eine **Konsole**, die die Daten speichert und an den **weatherlink.com Server** schickt. Dieser Server hat zwei APIs, die vom **DB-Manager** benutzt werden um die Daten abzurufen und in einer **MySQL Datenbank** zu speichern. Von dort kann die **Website** mit PHP und MySQLi auf die Daten zugreifen, um sie darzustellen.

Zusätzlich wird **phpMyAdmin** zum Testen und Debuggen verwendet.

Im weiteren wird der Setup-Prozess zur Entwicklung am eigenen Computer erläutert.
Den Setup-Prozess an der Raspberry Pi sowie wichtige Informationen zum Betrieb derselben finden sich [hier](RaspberryPi.md)

### **Docker**
Docker ist eine clevere Methode, um Software zu isolieren und für verschiedene Entwickler ohne Probleme zugänglich zu machen. Docker wird verwendet, um große Teile dieses Setups auszuführen. Du kannst es [hier](https://www.docker.com/) herunterladen. Nachdem Du es erfolgreich auf Deinem Computer installiert hast, kannst du damit beginnen, die verschiedenen Elemente zu erstellen, die das Setup benötigt.

Mit Docker kannst du Webserver oder Datenbanken ohne eine komplizierte Einrichtung auf deinem Computer ausführen. Das einzige, was du brauchst, ist ein sogenanntes **Image**, eine Art Bauplan der Software, die du mit Docker laufen lassen möchtest.  
Es gibt viele Images für sehr unterschiedliche Anwendungen. Du kannst sie alle im [Docker-Hub](https://hub.docker.com/) finden. Nachdem du ein Image ausgewählt hast, kannst du es herunterladen. Du kannst auch einfach das Image verwenden, um einen Container zu erstellen, ohne es davor herunter zu laden und Docker wird diesen Schritt automatisch durchführen.

Ein **Container** ähnelt einer virtuellen Maschine, ist aber viel leichter, aber dennoch vom Rest des Betriebssystems isoliert.  
Um einen Container zu erstellen, gibt es mehrere Möglichkeiten. Die erste ist die einfachste. Führe einfach den Befehl `docker run [OPTIONS] IMAGE` aus. Dieser Befehl ist der beste Weg, um einfache Docker-Setups zu erstellen.  
Es gibt viele optionale Parameter für diesen Befehl, aber die wichtigsten sind:
```
    -d -> führt den Container im Hintergrund aus
    -e -> Umgebungsvariablen festlegen
    -i -> den Container interaktiv halten
--name -> den Namen des Containers festlegen
    -p -> einen Port des Hosts mit einem Port des Containers verbinden
  --rm -> den Container entfernen, nachdem er gestoppt wurde
    -v -> einen Host-Ordner auf einen Container-Ordner montieren
```
Wenn ein run-Befehl ausgeführt wird, wird der Container gebaut und gestartet.

Um einen Container zu starten oder zu stoppen, gib einfach `docker start/stop CONTAINERNAME` ein. Mit `docker ps` kannst du alle laufenden Container sehen.

Du kannst neue Images mit einem `Dockerfile` erstellen. Diese Datei ist im Grunde ein Textdokument, welches Docker mitteilt, was im Image geändert werden soll.  
Wenn du mehrere Container erstellen willst, gibt es `docker compose`. Das ist ein Werkzeug, um verschiedene Container zu definieren und wie sie voneinander abhängen.

Eine weitere wichtige Sache ist Networking in Docker, aber dazu später mehr.

### **Docker-Container für MySQL**
Um den MySQL-Container zu erstellen, musst du nach der neuesten Version des offiziellen MySQL-Docker-Images auf [Docker-Hub](https://hub.docker.com/) suchen und diese als Tag verwenden. Dann musst du diesen Befehl ausführen, wobei TAG durch den zuvor gefundenen Tag ersetzt wird:
```
docker run -d --name mysql-db -p 3306:3306 -v /mysql-db-con:/con -e MYSQL_PASSWORD=root -e MYSQL_DATABASE=my-db mysql:TAG
```
Nun wird Docker das Image herunterladen und den Container starten.

Falls du Windows benutzt, kann es sein das der Befehl nicht funktioniert, weil die Pfade zu den Dateien anders geschrieben werden. In dem Fall musst du ein wenig experimentieren oder recherchieren.

Du kannst `docker ps` verwenden, um zu überprüfen, ob der Container läuft.

### **Docker-Container für phpMyAdmin****
Um phpMyAdmin zum Laufen zu bringen musst du den Befehl 
```
docker run -d --name myadmin -p 8081:80 -e PMA_HOST=mysql-db phpmyadmin
```
ausführen. Wenn der Container läuft kannst du deinen Browser öffnen und `localhost:8081` eingeben. Nun solltest du eine Website sehen, auf der du dich anmelden musst.

### **Docker-Networking**
Damit du mit phpMyAdmin auf deine Datenbank zugreifen kannst, musst du die beiden Container miteinander verbinden. Dafür musst du ein Netzwerk einrichten.
```
docker network create sqladmin
docker network connect sqladmin mysql-db
docker network connect sqladmin myadmin
```
Der erste Befehl erstellt ein neues Netzwerk mit dem Namen `sqladmin`. Die beiden anderen Befehle verbinden die beiden container `mysql-db` und `myadmin`
mit dem Netzwerk.  
Versuche nun dich mit dem Benutzer `root` und dem temporären Passwort `root` bei phpMyAdmin einzuloggen. Nun solltest du eine grafische Oberfläche sehen, mit der du die Datenbank einsehen, verwalten und verändern kannst.

### **Einrichten der Datenbank**
Damit der DB-Manager die Daten in die Datenbank schreiben kann, muss die Datenbank eine bestimmte Tabellenstruktur besitzen. Sonst läuft der Schreibbefehl ins Lehre.  
Um diese Tabellenstruktur zu erstellen musst du die Datei `setup.sql` im Ordner `setup` in phpMyAdmin importieren. Diese Aktion führt die SQL-Befehle, die in der Datei stehen aus. Diese initiieren eine neue Tabelle und definieren die Spalten mit ihren Eigenschaften.  
Eine andere Methode um diese Befehle auszuführen ist im Terminal. Dazu musst du eine bash Shell in dem Container der Datenbank ausführen. Das geht entweder mit der Benutzeroberfläche von Docker oder mit dem Befehl 
```
docker exec -it mysql-db /bin/bash
```
Der nächste Befehl wird im Container ausgeführt. Davor muss allerdings der .sql File in den Ordner gelegt werden, der beim Setup des Containers auf den Container-Ordner `/con` montiert wurde: `/mysql-db-con`. Falls du Windows benutzt hast, kann es sein dass die Pfade anders heißen.
```
mysql -u root -p mysql-db < /con/setup.sql
```
Dieser Befehl importiert den File im montierten Ordner in die Datenbank, also führt die SQL-Befehle aus.

Zusätzlich zum `setup.sql` file gibt es auch noch einen `sample-data.sql` file. Dieser enthält 100 Datenpunkte, mit denen du das Programm in Zukunft testen kannst.

### **Docker-Container für die Website**
Um die Website zum laufen zu bringen, muss ein weiterer Container erstellt werden. Allerdings braucht dieser eine Extrabehandlung mit einem Dockerfile.  
Den Dockerfile den du dafür brauchst findest du ebenfalls im Ordner `setup`. Diesen musst du nun in einen leeren Ordner bewegen. Dann navigierst du mit dem Terminal in den Ordner und führst folgendes aus:
```
docker build -t php-apache-mysqli .
```
Die `-t` option legt einen Tag für das erstellte Image fest. Der Punkt repräsentiert den Ordner, in dem du dich mit dem Terminal befindest.  
Der `build` Befehl sucht nach einer Datei mit dem Namen `Dockerfile` und benutzt ihn um das neue Image zu erstellen. Nun musst du nur noch den Container mit dem Image erstellen.
```
docker run -d --name Website -v "$PWD":/var/www/html -p 8080:80 website
```
In den Ordner, in dem du dich gerade befindest müssen auch alle Website files, die in Zukunft zu Github hinzugefügt werden.

Der Befehl `"$PWD"` ist ähnlich wie der Punkt, den wir vorhin benutzt haben. Er zeigt auf das gerade verwendete Verzeichnis.  
Falls das nicht funktioniert musst du herausfinden, wie dieser Befehl in der Shell geschrieben wird, die du benutzt.

Nun müssen wir noch die Website mit der Datenbank verbinden. Dafür musst du ein weiteres Docker-Netzwerk einrichten.  
In Zukunft wird es einen Weg geben, die Login Daten für die Website abzulesen.

Nun solltest du die Website über `localhost:8080` im Browser erreichen können.

### **git-secret**
Git-secret ist ein Werkzeug, um die Dateien mit sensitiven Daten zu verschlüsseln, bevor sie auf Github gestellt werden.  
Das einrichten von git-secret ist eines der letzten größeren Hindernisse, bevor der DB-Manager endlich rund laufen kann.

Wenn du kein aktiver Teil des Schulprojektes bist, sondern nur einen Beitrag leisten willst ist dieser Schritt für dich nicht nötig. Am besten ist es, wenn du in den unverschlüsselten Files die Daten mit deinen eigenen ersetzt. Stelle aber sicher, dass du diese veränderten Files nicht aus versehen auf Github stellst.  

Git-secret beruht auf `GPG`, einer Verschlüsselungssoftware die weltweit eingesetzt wird.

Auf **MacOS** musst du für die Installation zuerst **Homebrew** installieren. Das ist ein Werkzeug, mit dem sich verschiedene Anwendungen auf deinem Computer installieren lassen. Wie genau du das machst siehst du [hier](https://docs.brew.sh/Installation). Als nächstes musst du folgenden Befehl in deinem Terminal ausführen:
```
brew install git-secret
```
Mit diesem Befehl wird git-secret sowie GPG und ein paar andere Dinge installiert, von denen git-secret abhängig ist.

Auf **Windows** ist es etwas komplizierter, da du zuerst [WSL](https://learn.microsoft.com/de-de/windows/wsl/install) (Windows Subsystem for Linux) herunterladen musst.  
Wenn du das gemacht hast, musst du im WSL Terminal folgendes ausführen:
```
git clone https://github.com/sobolevn/git-secret.git git-secret
cd git-secret && make build
PREFIX="/usr/local" make install
```

Mehr Informationen zur Installation findest du [hier](https://git-secret.io/installation)

Um git-secret einzurichten muss ein Mitglied des Schulprojekts dir Zugang verschaffen.
Wenn du es aber für dich alleine verwenden willst gibt es [hier](https://git-secret.io/) die englische Anleitung zur Installation.

Wenn du nun den DB-Manager ausführst, solltest du sehen, ob er sich mit der Datenbank und der API verbinden kann.  
Wenn irgendetwas nicht funktioniert und du die Lösung für das Problem nicht findest, kontaktiere ein Mitglied des Schulprojekts, oder schreibe ein Issue. Wenn alles läuft, hast du erfolgreich das Setup abgeschlossen. 

## Bedienung

### **Die Inbetriebnahme**
Bevor der DB-Manager gestartet werden kann, muss man in der Befehlszeile zuerst in den Ordner des DB-Managers [navigieren](wichtige Befehle)
Bei der Inbetriebnahme des DB-Managers mit dem Aufruf der `src/main.py` Datei mit dem `python3` Interpreter erscheinen nach wenigen Sekunden einige Statusmeldungen über die Verschiedenen Bestandteile des Setups. Zuerst werden Anfragen an die **Weatherlink Api V1** und die **Weatherlink Api V2** gesendet, die prüfen, ob diese verfügbar sind. Dann wird die Verbindung und die Schreibe- und Lesemöglichkeit für die **Datenbank** überprüft.
Ist eine Verbindung zur **Api1** sowie zur **Datenbank** möglich, wird der **Request Timer** gestartet (vorausgesetzt, diese Funktionalität ist in den Einstellungen aktiviert). Dieser ruft automatisch jede halbe Stunde die Daten der **Api1** ab und speist sie in die **Datenbank** ein. Mehr zum Request Timer findet sich [hier](#reqtimer)

### **Command Line Interface**

Das Command Line Interface (cli) bietet einige Möglichkeiten den DB-Manager zu steuern. Generell kann der Befehl `help` verwendet werden, um eine Auflistung aller Befehle zu sehen. `help` kann dann erneut verwendet werden, um genauere Informationen über die einzelnen Befehle zu erhalten. Dazu schreibt man den fraglichen Befehl einfach hinter help (z.B. Zum Beispiel `help reqTimer`). Bei allen Befehlen außer `restart` und `quit` kann man ebenfalls einfach den Befehl selbst benutzen, um mehr Informationen über die Bedienungsweise zu erfahren. Grundsätzlich geht das bei allen Befehlen, die mehrere Optionen bereitstellen wie `database`.

reqTimer
--------
Der Request Timer (abgekürzt `reqTimer`) ist dafür zuständig während dem dauerbetrieb regelmäßig Daten für die Datenbank zu sammeln. Diese Aufgabe wird als **Persistierung** bezeichnet. Ist der ReqTimer aktiviert, läuft er selbstständig im Hintergrund und zeigt regelmäßig Meldungen über die Anfragen, die er tätigt.

Die Befehle `start`, `stop`, `silent` und `show` können dazu verwendet werden, den ReqTimer zu starten, zu stoppen, die Nachrichten zu verbergen oder wieder zu zeigen.

config
------
Der `config` Befehl wird verwendet, um die Konfiguration des DB-Managers zu verändern. Die Konfiguration wird in zwei separaten .json Dateien abgespeichert. Die eine Datei `config.json` enthält alle Informationen abgesehen von denen, die nicht auf github veröffentlicht werden sollten, wie Passwörter, Api-Token und Benutzernamen sowie Mail-Adressen. Diese werden separat in der von git-secret geschützten Datei `dat.json` gespeichert. Beim Start des DB-Managers werden beide Dateien eingelesen und zusammengelegt und am Ende wieder getrennt gespeichert.
Separat dazu steht die `error_msg_config.json` Datei, die nur verwendet wird, wenn Warn-E-Mails versendet werden müssen. Diese ist auch (noch) nicht vom DB-Manager aus veränderbar.

Die Konfiguration besteht aus mehreren Sektionen:

---
Die `db` Sektion enthält alle Informationen über den Zugang der **Datenbank**.
- `host`: Die Adresse des Hosts also der Maschine, auf der die Datenbank läuft. Hier: `127.0.0.1` (localhost/loopback)
- `port`: Die Port-Nummer der Datenbank. Standardmäßig: `3306`
- `user`: Der Benutzername für den Zugang zur Datenbank.
- `password`: Das Passwort für den Zugang.
- `database`: Der Name der Datenbank. (Das Datenbank-Programm an sich unterstützt mehrere Datenbanken.)
- `timeoutMs`: Die Zeit in Millisekunden, die der DB-Manager auf eine Antwort der Datenbank wartet, bevor er die Anfrage abbricht.
- `mendStartTime`: Das Datum, vor dem der DB-Manager nicht nach Lücken in der Datenbank sucht, weil da noch keine Daten gesammelt wurden. Format: `[Jahr],[Monat],[Tag],[Stunde],[Minute],[Sekunde]` 
---
Die `Api1` Sektion enthält alles Nötige für den Zugang zur **Weatherlink Api V1**
- `url`: Die URL der Weatherlink Api V1: `https://api.weatherlink.com/v1/NoaaExt.json`
- `user`: Der Benutzername für den Zugang bei [weatherlink.com](https://weatherlink.com)
- `pass`: Das Passwort für den Zugang bei [weatherlink.com](https://weatherlink.com)
- `apiToken`: Geheimes Token zur Verifizierung der Anfrage
- `timeoutMs`: Die Zeit in Millisekunden, die der DB-Manager auf eine Antwort der Api wartet, bevor er die Anfrage abbricht.
- `dataMaxAge`: Maximales Alter der Daten in Minuten, bei dem der DB-Manager keinen [`WStOfflineError`](#errors) erzeugt.
---
Die `Api2` Sektion enthält alles Nötige für den Zugang zur **Weatherlink Api V2**
- `url`: Die URL der Weatherlink Api V2: `https://weatherlink.github.io/v2-api/`
- `api-key`: Die ID des Benutzers der Api
- `api-secret`: Geheimnis zur Authentifizierung der Anfrage
- `stationID`: Die ID der Wetterstation, erhalten durch einen speziellen Api Aufruf.
- `timeoutMs`: Die Zeit in Millisekunden, die der DB-Manager auf eine Antwort der Api wartet, bevor er die Anfrage abbricht.
---
Die `requestTimer` Sektion enthält alle Informationen über den **Request Timer**
- `timer_at_startup`: Entscheidet, ob der Request Timer beim Start des Programmes direkt gestartet wird, wenn alle Bereiche funktionieren.
- `show_message`: Entscheidet, ob der Status einer Anfrage im Terminal gezeigt wird oder nicht.

debug
-----
Der `debug` Befehl sollte im normalen Betrieb nicht verwendet werden. Er stellt verschiedene Funktionen zur Verfügung, mit deren Hilfe man die Funktionalität des Setups überprüfen kann.

Diese Funktionen sind:

- `add`: Füge eine Zeile mit aktuellen Daten zur **Datenbank** hinzu. Diese Aktion gleicht einer normalen Anfrage des **Request Timers**.
- `dAdd`: Führe die selbe Aktion wie bei `add` aus, nur, dass die Aktion im **Request Timer** Thread ausgeführt wird. Dafür muss der **Request Timer** aktiv sein.
- `rm`: Entferne die zuletzt hinzugefügte Zeile der **Datenbank**. Dafür gedacht, `add` und `dAdd` Aktionen rückgängig zu machen.
- `reqApi1`: Sende eine Anfrage an die **Weatherlink Api V1** und speichere die vollständige Antwort als .json Datei im Ordner `requests/`
- `reqApi2`: Sende eine Anfrage an die **Weatherlink Api V2** und speichere die vollständige Antwort als .json Datei im Ordner `requests/`
- `sendMail`: Führe die Funktion `debug_email()` des Moduls `emailMessages.py` aus. Diese Funktion dient nur der Entwicklung, weshalb sie normalerweise keine Funktion erfüllt (also leer ist).

quit/restart
------------
Der Befehl `quit` beendet das Programm, nachdem die Einstellungen (die config.json und die dat.json Datei) wieder separiert und gespeichert wurden.

Der `restart` Befehl tut im Prinzip das selbe, mit nur wenigen Veränderungen. Zusätzlich zu den Einstellungen, wird auch noch die Liste der verwendeten Befehle in der versteckten Datei `.cmd_history` gespeichert. Dann ruft sich das Programm selbst auf, bevor es sich beendet. So kann während der Entwicklung der veränderte Source-Code gestartet werden, ohne den Komfort des Befehls-verlaufes einzubüßen.

### **Fehlermeldungen**
Der DB-Manager ist so geschrieben, dass er selbstständig auf alle Fehler die während des Betriebs auftauchen reagieren kann. Davon ausgenommen sind nur die speziellen Fehlermeldungen aus dem Modul `customExceptions.py`. Diese treten auf, wenn zum Beispiel die Verbindung mit der Datenbank fehlgeschlagen ist. Also Dinge, die nicht vom Programm selbst korrigiert werden können. Tritt so ein Fehler während des Betriebs des Request Timers auf, wird eine Warn-Email an eine Liste von mail-Adressen verschickt, in der die möglichen Gründe für den Fehler erläutert werden.

- `DBConnectionError`: Die Verbindung zur Datenbank ist fehlgeschlagen.
    - Die Datenbank könnte nicht aktiv sein
    - Die Konfiguration für die Verbindung könnte nicht korrekt sein
    - Die Login-Informationen zur Datenbank könnten nicht stimmen.
- `DBWritingError`: Das schreiben in die Datenbank hat eine Fehlermeldung verursacht.
    - Die Struktur der Datenbank könnte nicht stimmen
    - Das Format der SQL-Anfrage des DB-Managers könnte falsch formatiert sein
- `DBNoDataReceivedError`: Es wurden keine Daten in der Datenbank gefunden.
    - Die Datenbank könnte nicht (korrekt) eingerichtet sein
    - Die SQL-Anfrage könnte an die falsche Datenbank-Tabelle gerichtet sein
- `DBTimeoutError`: Die Datenbank hat nicht geantwortet.
    - Die Datenbank könnte nicht (mehr) in Betrieb sein
    - Die Verbindung zur Datenbank könnte schlecht sein
- `ApiConnectionError`: Die Verbindung mit der Servern von Davis Instruments konnte nicht aufgenommen werden. die Anfrage ist deshalb gescheitert.
    - Die Internetverbindung könnte schlecht sein
    - Der Server von Davis Instruments könnte gerade nicht erreichbar sein
- `DataIncompleteError`: Die Daten von der Wetterstation sind unvollständig.
    - Die Kabel zu einzelnen Instrumenten an der Wetterstation könnten beschädigt sein
    - Das Kabel zwischen der Wetterstation und der Konsole könnte beschädigt sein
- `WStOfflineError`: Die Wetterstation ist nicht mit dem Internet verbunden
    - Das Lan-Kabel könnte aus gesteckt sein
- `ApiTimeoutError`: Der Server von Davis Instruments hat nicht geantwortet
    - Die Verbindung mit den Internet könnte schlecht sein

### **Datenbank Administration**

### Wichtige befehle im Terminal
zum Navigieren
zum lesen und verändern von text dateien
zum Verbinden mit der RPi
    ssh
    mount

## Entwicklung

Struktur:

    - Einleitung
        - DB-Manager + Raspberry Pi
        - Dokumentation beruht auf den Docstrings
    - Verhalten mit dem Code
        - Datensicherheit
        - Dokumentation
        - Bewahrung und Akzeptanz von anderem Code
    - Verhalten an der Raspberry Pi
        - use backups for the config files
    - Workflow
    - Funktionsweise des Programmes
        - grundstruktur
        - config files
            -> values and where to find them (DID Device id -> written on the data logger of the console)
    - besonderheiten
        - hidden files
            .remaining_gaps
	        .cmd_history
        - wind direction in letters and not in numbers
            download files use letters too
        - Zeit CET ohne DST
    - nicht doc-string dokumentiertes


Workflow:
- getting ready for developing something new
- create branch from main or switch to branch
- pulling (if switched to branch)
- git secret reveal
- developing
- git secret hide
- commit if finished
- push and merge (pull request on github)

