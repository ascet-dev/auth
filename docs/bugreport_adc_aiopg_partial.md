# Баг-репорт: `Base.partial()` мутирует исходную модель (adc-aiopg 1.1.1)

> **Статус: исправлено в adc-aiopg 1.2.0.** Проект обновлён, локальный обход
> (`optional()` в `web/endpoints/admin/schemas.py`) удалён, схемы используют
> штатный `Base.partial()`. Воспроизведения ниже на 1.2.0 больше не работают:
> исходная модель не меняется, схемы не зависят от порядка вызовов, partial
> принимает явный `null`. Документ оставлен как история находки.
>
> В фиксе учтены и смежные замечания: `partial()`/`only()`/`exclude()` строятся
> на `Base` (partial **больше не подкласс** исходной модели), аннотация partial-полей
> становится `Optional`, `only()` ругается на несуществующие имена полей.

**Библиотека:** `adc-aiopg` 1.1.1, файл `adc_aiopg/types.py`
**Severity:** высокая — тихо снимает обязательность полей у модели, из которой строилась схема.
Проявляется отложенно, поэтому в тестах на «свою» схему не видно.

## Суть

`Base.partial()` берёт объекты `FieldInfo` **исходной** модели и присваивает им
`default = None`, вместо того чтобы работать с копиями:

```python
@classmethod
def partial(cls: t.Type[T]) -> t.Type[T]:
    fields = {k: (v.annotation, v) for k, v in cls.model_fields.items()}  # v — FieldInfo самой cls
    for field in fields:
        fields[field][1].default = None                                   # мутация cls.model_fields
    return create_model(f'Partial{cls.__name__}', __base__=cls, **fields)
```

После вызова `cls.model_fields` навсегда испорчен: все поля помечены необязательными.

## Воспроизведение

Модель: `ClientApp(BaseModel)` с обязательными `key: str`, `name: str`.

### 1. Метаданные модели портятся сразу

```python
ClientApp.model_fields["key"].is_required()   # True
ClientApp.partial()
ClientApp.model_fields["key"].is_required()   # False  ← исходная модель изменена
```

### 2. Порча материализуется в поведении при rebuild

Скомпилированная core-схема не пересобирается автоматически, поэтому сразу после вызова
валидация ещё работает. Но любой `model_rebuild` (в т.ч. неявный — при отложенных
аннотациях, дозагрузке форвард-рефов, пересборке в фреймворке) фиксирует испорченные поля:

```python
ClientApp.partial()
ClientApp.model_rebuild(force=True)
ClientApp()          # проходит валидацию!
# {'id': None, 'key': None, 'name': None, 'access_token_ttl_sec': None, ...}
```

Для табличной модели это означает попытку записать `NULL` в `NOT NULL` колонки —
ошибка вылезет уже на уровне БД, далеко от места вызова `partial()`.

### 3. Результат зависит от порядка вызовов (самое коварное)

Схемы, построенные из модели **после** `partial()`, молча теряют обязательные поля:

```python
before = ClientApp.only("key", "name")
before.model_fields["key"].is_required()   # True

ClientApp.partial()

after = ClientApp.only("key", "name")
after.model_fields["key"].is_required()    # False
after()                                    # валиден без key и name
```

То есть один вызов `partial()` где-то в модуле схем меняет валидацию **других** схем,
собранных ниже по файлу. Для API это тихое исчезновение обязательных полей в запросах.

### Что НЕ подтвердилось (проверено, для полноты)

- Порча **не** протекает на другие модели: `FieldInfo` наследуемых полей (`id`, `created`,
  `archived`) у каждого подкласса свои, `ClientApp.model_fields["id"] is Session.model_fields["id"]`
  → `False`. Радиус поражения — только тот класс, на котором вызван `partial()`, и всё,
  что от него произведено после вызова.
- `only()` / `exclude()` сами по себе не мутируют исходную модель.

## Предлагаемый фикс

Копировать `FieldInfo` перед изменением, а не менять чужой объект:

```python
import copy

@classmethod
def partial(cls: t.Type[T]) -> t.Type[T]:
    fields = {}
    for name, field in cls.model_fields.items():
        clone = copy.deepcopy(field)
        clone.default = None
        fields[name] = (field.annotation | None, clone)   # аннотация тоже должна стать Optional
    return create_model(f'Partial{cls.__name__}', __base__=cls, **fields)
```

Два момента помимо копирования:

1. **Аннотация.** Сейчас меняется только `default`, а тип остаётся прежним (`str`), поэтому
   явный `null` в PATCH-запросе не пройдёт валидацию, хотя поле «необязательное».
   Для partial-схем корректно `annotation | None`.
2. **`__base__=cls`.** Для табличной модели наследование может задеть SQLAlchemy-регистрацию
   (переопределение таблицы). Если partial-схемы задуманы как DTO, надёжнее `__base__=Base`,
   как это уже сделано в `only()` / `exclude()`.

## Регрессионный тест

```python
def test_partial_does_not_mutate_source_model():
    class M(Base):
        a: str
        b: int

    assert M.model_fields["a"].is_required()

    P = M.partial()

    # исходная модель не тронута
    assert M.model_fields["a"].is_required()
    M.model_rebuild(force=True)
    with pytest.raises(ValidationError):
        M()

    # partial-схема действительно необязательная и принимает явный null
    assert not P.model_fields["a"].is_required()
    assert P().a is None
    assert P(a=None).a is None


def test_derived_schema_is_order_independent():
    class M(Base):
        a: str

    M.partial()
    assert M.only("a").model_fields["a"].is_required()
```

## Смежные замечания по тому же файлу (не баги, но стоит посмотреть)

1. **`only()` / `exclude()` теряют конфиг и валидаторы исходной модели**, потому что строятся
   с `__base__=Base`. Проверено: у `ClientApp` в `model_config` есть ключ `exclude`
   (`{'created', 'updated', 'archived'}`), у `ClientApp.only('id', 'key')` его уже нет;
   field-валидаторы исходной модели в производную тоже не переезжают. Если это осознанное
   решение — стоит написать в докстроке, иначе производные схемы будут «почти как модель»,
   но без её правил.

2. **Затенение параметра в `only()`:**

   ```python
   def only(cls, *fields: str):
       fields = {k: (v.annotation, v) for k, v in cls.model_fields.items() if k in fields}
   ```

   Работает (comprehension дочитывает старое значение до присваивания), но читается как
   ошибка и ломается от любой перестановки строк. Просится отдельное имя переменной.

3. **Имена производных моделей детерминированы** (`ClientAppOnly_id_key`), так что два вызова
   с одинаковым набором полей дают одинаковое имя разных классов — в OpenAPI-схеме это
   потенциальная коллизия компонентов.

## Как это обходится у нас сейчас

В `web/endpoints/admin/schemas.py` есть локальный `optional(model, name)` с `deepcopy`
и `annotation | None` — временная замена. После фикса в библиотеке его нужно удалить
и перейти на `Base.partial()`.
