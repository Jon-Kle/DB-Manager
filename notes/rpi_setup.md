# Raspberry pi Einrichtung
Eine Dokumentation aller Veränderungen an dem RPi, um den langzeitbetrieb der Programme zu garantieren.

Damit diese Dokumentation weiterhin ihren Zweck erfüllen kann, sollten auch alle weiteren Veränderungen an dem RPi hier chronologisch dokumentiert werden.

## Inhalt:
- [USB-Bootfähigkeit](#usb-bootfähigkeit)
- [Betriebssystem](#betriebssystem)
- [WLAN Verbindung](#wlan-verbindung)
- [wpa_supplicant Log Datei](#wpa_supplicant-log-datei)
- [SSH](#ssh)
- [Aktionen nach Zeitplan (Cronjobs)](#aktionen-nach-zeitplan-cronjobs)
- [exFAT Driver](#exfat-driver)

---
## USB-Bootfähigkeit
### **Warum?**
Das Ursprüngliche Speichermedium eines Raspberry Pi ist eine SD-Karte. Diese hat jedoch nur eine begrenzte Kapazität und ist außerdem nicht so langlebig wie ein USB-Stick. Daher wird der Raspberry Pi mit letzterem betrieben. Auf diesem `64GB` USB-Stick liegen also alle Dateien des Betriebssystems. Daher sollte der USB-Stick nie während der Laufzeit entfernt werden, da dies zur Korruption des Betriebssystems führen kann.
### **Wie?**
https://www.elektronik-kompendium.de/sites/raspberry-pi/2404241.htm

---
## Betriebssystem
### **Was?**
Der Raspberry Pi läuft mit dem `Raspberry Pi OS Lite (64bit)`. Das heißt, der RPi hat keine Desktop Oberfläche, da er die Meiste Zeit autonom laufen wird.
### **Wie?**
Das Betriebssystem wurde mit Hilfe des `Raspberry Pi Imagers` auf den USB-Stick gespielt.
Dabei muss auch gleich die ssh Verbindung eingerichtet werden.

Download: https://www.raspberrypi.com/software/

---
## WLAN Verbindung
**nicht notwendig**
### **Was?**
Während der Entwicklung ist der Raspberry Pi über WLAN mit dem Internet verbunden. Später wird er aber mit Ethernet verbunden sein.
### **Wie?**
Die Konfiguration über `raspi-config` funktioniert nicht, daher muss das WLAN direkt über die Kommandozeile mit `wpa_supplicant` eingerichtet werden.

https://www.elektronik-kompendium.de/sites/raspberry-pi/1912221.htm

---
## wpa_supplicant Log Datei
**nicht notwendig**
### **Was?**
Während der Entwicklung kam es immer wieder zu WLAN Ausfällen. Um zu Verstehen, was falsch läuft, wurde der `wpa_supplicant` so konfiguriert, dass er seine Aktionen in einen `logfile` schreibt. Dieser befindet sich in `/var/log/wpa_supplicant.log`.
### **Wie?**
Eigentlich ist das für den Langzeitbetrieb nicht wichtig und auch nicht hinderlich, trotzdem hier der Link zur Erklärung:

https://netbeez.net/blog/linux-wireless-engineers-read-wpa-supplicant-logs/

---
## WLAN Stabilisation mit iwconfig
**nicht notwendig**
### **Was?**
Beim Betrieb über WLAN kam es immer wieder dazu, dass nach dem per [SSH](#ssh) herbeigeführten Neustart der RPi die Verbindung mit dem WLAN nicht wieder aufgebaut hatte. Dieses Problem lies sich am Ende mit Hilfe des Befehls `iwconfig` lösen.
### **Wie?**
Die Zeile `sudo iwconfig wlan0 power off` deaktiviert das `Power Management` des RPis. Danach war das Problem behoben.

https://forums.raspberrypi.com/viewtopic.php?t=188891

---
## SSH
**nicht notwendig wenn die configuration bereits im Imager stattfand**
### **Was?**
SSH steht für Secure Shell und ist die einfachste Möglichkeit von außerhalb auf ein Gerät zuzugreifen, ohne einen Bildschirm und eine Tastatur anzuschließen.
Diese Betriebsweise wird auch `headless` (kopflos) genannt.
Das macht SSH aber auch zu einem der vielversprechendsten Angriffspunkte für Hacker.
### **Wie?**
https://roboticsbackend.com/enable-ssh-on-raspberry-pi-raspbian/#Enable_ssh_on_Raspberry_Pi_4_with_a_monitor_and_keyboard

Für den Entwicklungs- und Testprozess wird noch ein passwort verwendet. Später für den Standardbetrieb wird allerdings für bessere Sicherheit das `public key authentication` Verfahren verwendet werden.
https://de.wikipedia.org/wiki/Public-Key-Authentifizierung

---
## Aktionen nach Zeitplan (Cronjobs)
### **Was?**
Der Raspberry Pi soll am ersten Tag jedes zweiten Monats um 00:15 einen Neustart machen. Diese und auch andere zeitlich festgelegte Aktionen lassen sich mit `crontab` konfigurieren.
### **Wie?**
https://www.stetic.com/developer/cronjob-linux-tutorial-und-crontab-syntax/

Die Cronjobs werden immer mit `sudo` festgelegt

---
## exFAT Driver
### **Was?**
Im Entwicklungsprozess ist es immer wieder notwendig Dateien auf und von dem Raspberry Pi zu bewegen. Eine Möglichkeit dafür sind USB-Sticks. Diese verwenden häufig das `FAT-Dateisystem`, welches von dem RPi aber nicht standardmäßig unterstützt wird. Deshalb mussten dafür die beiden Pakete `exfat-fuse` und `exfat-utils` installiert werden.
### **Wie?**
Alle Installierten Pakete lassen sich mit dem Befehl `dpkg --get-selections` auflisten. Mehr zu den Paketen selbst gibt es hier:

https://pimylifeup.com/raspberry-pi-exfat/

(Um das richtige Laufwerk zum mounten zu finden: lsblk)

---
## Installation der Datenbank
### **Was?**
Im Betrieb auf dem RPi läuft die Datenbank nicht mehr in einem Docker-Container. Stattdessen läuft sie direkt auf dem Raspberry Pi. `MySQL` wurde in vielen Linux Applikationen durch `MariaDB` ersetzt, was sich aus MySQL entwickelt hat. Deshalb wird `MariaDB` installiert.
### **Wie?**
https://pimylifeup.com/raspberry-pi-mysql/

---
## Einrichtung der Datenbank

---
instalation und Konfiguration von apache2
--> keep backups of all config files

apache2 controls:
sudo service apache2 start
sudo service apache2 stop

sudo update-rc.d apache2 disable
sudo update-rc.d apache2 enable
sudo update-rc.d apache2 remove
---
instalation von PHP

https://www.chefblogger.me/2021/02/02/raspberry-pi-wie-installiere-ich-einen-webserver-mit-php-und-einer-datenbank/

---
instalation von phpmyadmin

---
Konfiguration von apache
-> phpmyadmin nur von gewissen ips aus zeigen
---
https ...?

---
downloading git

download newest python version (custom installation)
-> linking to new installation

python dependencies
pymysql

-----------

DID Device id -> written on the data logger of the console

why wind dir is displayed with letters and not numbers?
	-> download files use numbers too

handling time values in the db and the api

-----------

database gaps anleitung

sql file for creating the database

-----------
passw: root
usr: root

installing db
setting up db
creating database and table
-> dumpfile
https://pimylifeup.com/raspberry-pi-mysql/

todo -> phpmyadmin installation
https://pimylifeup.com/raspberry-pi-phpmyadmin/
possible with "OS light"?

host file (hosts)

code vom repo pullen

lsblk -f
tmux a
ctrl + b, d
ctrl + b, [

mount -f exfat /dev/sd... /media/exfat
umount dev/.....

git config --global --add save.directory /home/DB-Manager
git config --global --add save.directory /home/wetter



crontab -e -> reboot

rc.local -> on startup run "tmux new-session -d -c /home/DB-Manager -s DB-Manager sudo python3 src/main.py"