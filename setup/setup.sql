
SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

CREATE TABLE `weatherdata` (
  `entryDate` datetime DEFAULT NULL,
  `temp` float DEFAULT NULL,
  `pressure` float DEFAULT NULL,
  `hum` tinyint DEFAULT NULL,
  `windspeed` float DEFAULT NULL,
  `winddir` varchar(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT '---',
  `rainrate` float DEFAULT NULL,
  `uvindex` tinyint DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE `weatherdata`
  ADD UNIQUE KEY `entryDate` (`entryDate`);
COMMIT;