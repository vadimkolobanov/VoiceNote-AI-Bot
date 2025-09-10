import pytest

# Этот conftest располагается в tests/unit и перекрывает одноименные фикстуры
# более высокого уровня. Делает юнит-тесты независимыми от БД.

@pytest.fixture(autouse=True)
def clean_notes_table():
    # Заглушка для тяжелой фикстуры очистки БД из верхнего conftest.
    # Ничего не делаем специально.
    yield
