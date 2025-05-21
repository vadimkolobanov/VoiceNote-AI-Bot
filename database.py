import sqlite3


# Создание подключения к базе данных
def get_connection():
    conn = sqlite3.connect('my_database.db')
    return conn


# Создание таблицы пользователей
def create_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS users
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY,
                       name
                       TEXT
                       NOT
                       NULL,
                       age
                       INTEGER,
                       email
                       TEXT
                       UNIQUE
                   )
                   ''')
    conn.commit()
    conn.close()


# Функция для создания нового пользователя
def create_user(name, age, email):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
                       INSERT INTO users (name, age, email)
                       VALUES (?, ?, ?)
                       ''', (name, age, email))
        conn.commit()
    except sqlite3.IntegrityError as e:
        print(f"Ошибка при создании пользователя: {e}")
    finally:
        conn.close()


# Функция для получения всех пользователей
def get_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, age, email FROM users')
    users = cursor.fetchall()
    conn.close()
    return users


# Функция для получения пользователя по ID
def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
                   SELECT id, name, age, email
                   FROM users
                   WHERE id = ?
                   ''', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user


# Функция для обновления данных пользователя
def update_user(user_id, name, age, email):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
                       UPDATE users
                       SET name  = ?,
                           age   = ?,
                           email = ?
                       WHERE id = ?
                       ''', (name, age, email, user_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Ошибка при обновлении пользователя: {e}")
    finally:
        conn.close()


# Функция для удаления пользователя
def delete_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()


# Тестирование CRUD операций
if __name__ == '__main__':
    # Инициализация базы данных
    create_table()

    # Создание тестового пользователя
    create_user('John Doe', 30, 'john@example.com')

    # Вывод всех пользователей
    print("Все пользователи:")
    print(get_users())

    # Обновление пользователя
    update_user(1, 'Jane Doe', 25, 'jane@example.com')

    # Получение пользователя по ID
    print("\nПользователь с ID 1 после обновления:")
    print(get_user_by_id(1))

    # Удаление пользователя
    delete_user(1)

    # Проверка удаления
    print("\nПользователь с ID 1 после удаления:")
    print(get_user_by_id(1))