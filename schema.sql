-- Fresh schema: drops and recreates both tables.

CREATE DATABASE IF NOT EXISTS todo_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE todo_db;

DROP TABLE IF EXISTS task_events;
DROP TABLE IF EXISTS tasks;

CREATE TABLE tasks (
  id INT NOT NULL AUTO_INCREMENT,
  title VARCHAR(200) NOT NULL,
  description TEXT NULL,
  due_date DATE NULL,
  priority ENUM('low', 'medium', 'high') NOT NULL DEFAULT 'medium',
  status ENUM(
    'todo',
    'in_progress',
    'ready',
    'review',
    'done'
  ) NOT NULL DEFAULT 'todo',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_tasks_status (status),
  KEY idx_tasks_priority (priority),
  KEY idx_tasks_due_date (due_date),
  KEY idx_tasks_created_at (created_at)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

CREATE TABLE task_events (
  id INT NOT NULL AUTO_INCREMENT,
  task_id INT NOT NULL,
  from_status ENUM(
    'todo',
    'in_progress',
    'ready',
    'review',
    'done'
  ) NULL,
  to_status ENUM(
    'todo',
    'in_progress',
    'ready',
    'review',
    'done'
  ) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_task_events_task_id_created_at (task_id, created_at),
  CONSTRAINT fk_task_events_task
    FOREIGN KEY (task_id) REFERENCES tasks (id)
    ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;
