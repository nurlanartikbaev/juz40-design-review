# Дизайн-ревью JUZ40

Скилл для Claude сверяет дев с макетом в Figma и собирает расхождения скринами в вашем workspace.

## Что вы получите

Новую страницу в Figma. В карточке каждого расхождения есть:

- скрины макета и дева с рамкой на элементе;
- критичность: «Критично», «Важно» или «Мелочь»;
- таблица значений;
- ссылки на макет и дев.

Существующие страницы скилл не меняет. Если расхождений нет, скилл ничего не создаёт в Figma.

## Что нужно

- Claude с подключённой Figma и правом редактирования в workspace
- Google Chrome
- Python 3

## Установка

**Claude Desktop.** Скачайте [dist/juz40-design-review.skill](dist/juz40-design-review.skill) и откройте файл в Claude.

**Claude Code.** Выполните две команды:

```
/plugin marketplace add nurlanartikbaev/juz40-design-review
/plugin install juz40-design-review@juz40-design-review
```

## Как запустить

Напишите Claude:

```
Проведи дизайн-ревью
```

Claude попросит 3 ссылки:

1. Workspace в Figma: файл или проект, куда собрать скрины
2. Макет: фрейм или секция в Figma
3. Дев: адрес страницы на стенде

Если стенд требует вход, откроется отдельное окно. Введите логин и пароль в нём и закройте окно. Не отправляйте пароли в чат.

## Состав

| Путь | Назначение |
|---|---|
| `skills/juz40-design-review/SKILL.md` | Порядок работы |
| `skills/juz40-design-review/references/compare.md` | Допуски и критичность |
| `skills/juz40-design-review/scripts/devshot.py` | Скрины и значения стилей дева |
| `skills/juz40-design-review/assets/board_builder.js` | Сборка доски в Figma |
