
SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

CREATE DATABASE IF NOT EXISTS weather;
USE weather;

CREATE TABLE IF NOT EXISTS `data` (
  `entryDate` datetime DEFAULT NULL,
  `temp` float DEFAULT NULL,
  `pressure` float DEFAULT NULL,
  `hum` tinyint DEFAULT NULL,
  `windspeed` float DEFAULT NULL,
  `winddir` varchar(3) CHARACTER SET utf8mb4 DEFAULT '---',
  `rainrate` float DEFAULT NULL,
  `uvindex` tinyint DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE `data`
  ADD UNIQUE KEY `entryDate` (`entryDate`);
COMMIT;