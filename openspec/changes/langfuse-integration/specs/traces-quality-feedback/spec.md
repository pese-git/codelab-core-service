# traces-quality-feedback Specification

## Назначение

Возможность записи user feedback и scores (оценок качества) в traces для анализа качества работы агентов.

## ADDED Requirements

### Requirement: Запись оценок качества (scores) для traces

Система ДОЛЖНА позволять записывать feedback и оценки качества для traces.

#### Scenario: Запись оценки пользователя
- **WHEN** пользователь оставляет feedback на ответ агента (rating 1-5)
- **THEN** система записывает score в trace: {name: "user_satisfaction", value: rating/5.0, comment: feedback_text}

#### Scenario: Запись метрик качества
- **WHEN** система завершает LLM операцию
- **THEN** система может записать scores: {relevance: 0.95, accuracy: 0.88, helpfulness: 1.0}

### Requirement: API для записи scores

REST API ДОЛЖЕН предоставлять endpoints для записи scores в traces.

#### Scenario: POST endpoint для записи score
- **WHEN** клиент отправляет POST /traces/{trace_id}/scores с {name: "user_satisfaction", value: 0.8, comment: "Хороший ответ"}
- **THEN** система записывает score в Langfuse, возвращает 201 Created с ID записи

#### Scenario: Множественные scores для одного trace
- **WHEN** клиент отправляет несколько POST запросов на /traces/{trace_id}/scores
- **THEN** система записывает все scores, они доступны при получении trace

### Requirement: Валидация scores

Scores ДОЛЖНЫ быть валидированы перед записью.

#### Scenario: Валидация значения score
- **WHEN** клиент отправляет score с value вне диапазона [0, 1]
- **THEN** система возвращает 400 Bad Request с сообщением об ошибке

#### Scenario: Валидация trace_id
- **WHEN** клиент отправляет score с несуществующим trace_id
- **THEN** система возвращает 404 Not Found

### Requirement: Типы scores

Система ДОЛЖНА поддерживать различные типы scores для гибкой оценки.

#### Scenario: Стандартные типы scores
- **WHEN** система записывает scores
- **THEN** поддерживаются типы: user_satisfaction, relevance, accuracy, helpfulness, coherence, safety
- **AND** каждый score может содержать optional comment

#### Scenario: Custom scores
- **WHEN** код записывает score с custom name
- **THEN** система принимает custom names если они содержат только alphanumeric и underscore
- **AND** score успешно сохраняется

### Requirement: Агрегация scores для аналитики

Scores ДОЛЖНЫ быть доступны для агрегации и анализа.

#### Scenario: Получение average score
- **WHEN** клиент запрашивает GET /traces?agent=research_agent&metrics=average_user_satisfaction
- **THEN** система возвращает aggregated метрику: average_user_satisfaction: 0.85, count: 120
