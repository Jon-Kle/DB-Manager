# DB-Manager

[deutsche Version](de/README.md)

This program regularly collects weather data of a weather station from the [weatherlink website](weatherlink.com) of Davis Instruments and stores them in a MySQL database.

The code for the website to display the data will also be put on Github in the future.

This is a school project. If you want to contribute, please read the file [CONTRIBUTING.md](CONTRIBUTING.md).

## Index:
- [About this project](#about-this-project)
- [Setup](#setup)
    - [Docker](#docker)
    - [Docker container for MySQL](#docker-container-for-mysql)
    - [Docker container for phpMyAdmin](#docker-container-for-phpmyadmin)
    - [Docker networking](#docker-networking)
    - [Setting up the database](#setting-up-the-database)
    - [Docker container for the Website](#docker-container-for-the-website)
    - [git-secret](#git-secret)
- Usage
- Development

## About this project

This project started as an in-depth work by a former student in the year 2015. He created the website and a c++ program as an extension for the weather monitoring software that came with the weather station. He intended to run the entire setup locally at the school but never got to deploy his work.  
A few years later, I got to work on the code but I found that the c++ code was missing. So i replaced the c++ code and decided to change the setup and retrieve the data from Davis Instruments' servers via API. First, because the monitoring software would have had to run 24/7 on a Windows PC, and second, because this software was ancient. The DB-Manager is this replacement.

I personally hope, that other students will continue to work on this project. The **DB-Manager** is now nearly complete but for example an automatic database completion after an outage could be added.  
The **website** can be improved and expanded to display weatherdata in more ways. The only condition is that *the basic design of the website stays the same.*  
The student who designed it in the first place should recognize his work.

## Setup

The setup has the goal to bring the data from the weather station at the school to the website. To achieve this, a chain of different elements is necessary:

Connected to the **weather station** is a **console** that stores the data and sends it to the **weatherlink.com server**. This server has two APIs that are used by the **DB-Manager** to gather the data. Then it gets stored in a **MySQL Database**. From there the **website** can access it via MySQLi.  

In addition, **phpMyAdmin** is used to view the data from the database for testing and debugging.

### Docker
Docker is a clever way to isolate software and make it portable for different developers and is used to run big parts of this setup. You can download it [here](https://www.docker.com/). After you have successfully installed it on your computer, you can begin to build the different elements, the setup requires.

With Docker, you can run web servers or databases on your computer without a complicated setup. The only thing you need is a so called **image**, a kind of blueprint of the software you want to run.  
There are many images for very different applications. You can find them all in the [Docker-Hub](https://hub.docker.com/). After you picked an image, you can `pull` it onto your computer. You can also just use the image to create a container without downloading it and docker will do this step automatically.

A **container** is similar a virtual machine, but it much more lightweight, but is none the less isolated from the rest of the operating system.  
To create a container, there are multiple possibilities. The first one being the easiest. Just run the command `docker run [OPTIONS] IMAGE`. This command is the best way to create simple docker setups.  
There are many optional parameters for this command, but the most important ones are:
```
    -d -> run the container in the background
    -e -> set environment variables
    -i -> keep the container interactive
--name -> set the name of the container
    -p -> map a port from the host to a port from the container
  --rm -> remove the container after it is stopped
    -v -> mount a host directory to a container directory
```
When a run command is executed, the container gets built and started.

To stop or start a container, just type `docker start/stop CONTAINERNAME`. With `docker ps`, you can see all the containers running.

You can create new images with a `Dockerfile`. This file is basically a text document to tell docker what to change on the image.  
If you want to create multiple containers, there is `docker compose`. This is a tool to define different containers and how they depend on each other.

Another important thing is networking with docker, but that will come later.

### Docker container for MySQL
To create the MySQL container, you need to search for the latest version of the official MySQL Docker image on [Docker Hub](https://hub.docker.com/) and use that as the tag. Then you need to run this command, replacing TAG with the tag you found earlier:
```
docker run -d --name mysql-db -p 3306:3306 -v /mysql-db-con:/con -e MYSQL_PASSWORD=root -e MYSQL_DATABASE=my-db mysql:TAG
```
Now Docker will download the image and start the container.

You can use `docker ps` to check if the container is running.


### Docker container for phpMyAdmin
To get phpMyAdmin running you have to use the command 
```
docker run -d --name myadmin -p 8081:80 -e PMA_HOST=mysql-db phpmyadmin
```
When the container is running you can open your browser and type `localhost:8081`. Now you should see a website where you have to log in.

### Docker networking
In order to access your database with phpMyAdmin, you need to connect the two containers. For that, you need to set up a network.
```
docker network create sqladmin
docker network connect sqladmin mysql-db
docker network connect sqladmin myadmin
```
The first command creates a new network named `sqladmin`. The other two commands connect the two containers `mysql-db` and `myadmin` to the network you just created. 
Now try to log in to phpMyAdmin with the user `root` and the temporary password `root`. Now you should see a graphical interface where you can view, manage and modify the database.

### Setting up the database
In order for the DB Manager to write the data to the database, the database must have a certain table structure. Otherwise the write command will have no impact.  
To create this table structure you have to import the file `setup.sql` in the folder `setup` in phpMyAdmin. This action executes the SQL commands that are in the file. These initiate a new table and define the columns with their properties.  
Another method to execute these commands is in the terminal. For this you need to run a bash shell in the container of the database. This can be done either with Docker's user interface or with the command 
```
docker exec -it mysql-db /bin/bash
```
The next command will be executed in the container. Before that however, you need to put the .sql file in the folder that was mounted on the container folder `/con` during the setup. In our case `/mysql-db-con`. If you used Windows, the paths may be named differently.
```
mysql -u root -p mysql-db < /con/setup.sql
```
This command imports the file in the mounted folder into the database, so it executes the SQL commands.

In addition to the `setup.sql` file there is also a `sample-data.sql` file. This contains 100 data points with which you can test the program in the future.

### Docker container for the website
To get the website running, another container needs to be created. However, this one needs extra treating with a Dockerfile.  
The Dockerfile you need for this can also be found in the folder `setup`. Now you have to move it into an empty folder. Then you navigate with the terminal into the folder and execute the following:
```
docker build -t php-apache-mysqli .
```
The `-t` option specifies a tag for the built image. The dot represents the folder you are in with the terminal.  
The `build` command looks for a file named `Dockerfile` and uses it to create the new image. Now you just have to create the container with the image.
```
docker run -d --name website -v "$PWD":/var/www/html -p 8080:80 website
```
The folder you are currently in must also contain all website files that will be added to Github in the future.

The command `"$PWD"` is similar to the dot we used earlier. It points to the directory you are currently using.  
If that doesn't work you need to find out how to write this command in the shell you are using.

Now we still need to connect the website to the database. For that, you'll need to set up another Docker network.  
In the future, there will be a way to read the login information for the website.

Now you should be able to reach the website via `localhost:8080` in the browser.

### git-secret
Git-secret is a tool to encrypt the files with sensitive data before putting them on Github.  
Setting up git-secret is one of the last major obstacles before the DB manager can finally run smoothly.

If you are not an active part of the school project, but just want to contribute, this step is not necessary for you. The best thing to do is to replace the data in the unencrypted files with your own. But make sure you don't accidentally put these changed files on Github.  

Git-secret is based on `GPG`, an encryption software that is used worldwide.

On **MacOS** you have to install **Homebrew** first. This is a tool that allows you to install various applications on your computer. You can see exactly how to do this [here](https://docs.brew.sh/Installation). Next you need to run the following command in your terminal:
```
brew install git-secret
```
This command will install git-secret as well as GPG and a few other dependencies of git-secret.

On **Windows** it is a bit more complicated, because you have to download [WSL](https://learn.microsoft.com/de-de/windows/wsl/install) (Windows Subsystem for Linux) first.  
Once you have done that, you need to run the following in the WSL terminal:
```
git clone https://github.com/sobolevn/git-secret.git git-secret
cd git-secret && make build
PREFIX="/usr/local" make install
```

More information about the installation can be found [here](https://git-secret.io/installation)

To set up git-secret, a member of the school project must give you access.
If you want to use it on your own, you can find the installation instructions [here](https://git-secret.io/).

Now when you run the DB Manager, you should see if it can connect to the database and API.  
If something doesn't work and you can't find the solution to the problem, contact a member of the school project or write an issue. If everything works, you have successfully completed the setup. 

## Usage

## Development