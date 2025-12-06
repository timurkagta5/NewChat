"""
Скрипт для инициализации базы данных и создания тестовых данных
"""
from app import app, db, User, Chat, ChatMember, Message
import bcrypt

def init_database():
    with app.app_context():
        # Создаем таблицы
        db.create_all()
        print("✓ Таблицы созданы")
        
        # Проверяем, есть ли уже пользователи
        if User.query.first():
            print("⚠ База данных уже содержит данные")
            return
        
        # Создаем тестовых пользователей
        users_data = [
            {'username': 'reverse', 'tag': 'reverse', 'display_name': 'Reverse'},
            {'username': 'alex_dev', 'tag': 'alex_dev', 'display_name': 'Alex Developer'},
            {'username': 'maria_designer', 'tag': 'maria_designer', 'display_name': 'Maria Designer'},
            {'username': 'john_crypto', 'tag': 'john_crypto', 'display_name': 'John Crypto'},
        ]
        
        password = 'password123'
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        users = []
        for user_data in users_data:
            user = User(
                username=user_data['username'],
                tag=user_data['tag'],
                display_name=user_data['display_name'],
                password_hash=password_hash,
                status='offline'
            )
            db.session.add(user)
            users.append(user)
        
        db.session.commit()
        print(f"✓ Создано {len(users)} пользователей")
        
        # Создаем тестовые чаты
        chat1 = Chat(name='General Chat', is_group=True)
        chat2 = Chat(name='reverse', is_group=False)
        
        db.session.add(chat1)
        db.session.add(chat2)
        db.session.commit()
        
        # Добавляем участников
        for user in users:
            member = ChatMember(chat_id=chat1.id, user_id=user.id)
            db.session.add(member)
        
        member1 = ChatMember(chat_id=chat2.id, user_id=users[0].id)
        member2 = ChatMember(chat_id=chat2.id, user_id=users[1].id)
        db.session.add(member1)
        db.session.add(member2)
        
        db.session.commit()
        print("✓ Созданы тестовые чаты")
        
        # Добавляем тестовые сообщения
        msg1 = Message(chat_id=chat1.id, user_id=users[0].id, content='Привет всем!')
        msg2 = Message(chat_id=chat1.id, user_id=users[1].id, content='Привет! Как дела?')
        msg3 = Message(chat_id=chat2.id, user_id=users[0].id, content='Отправлено сообщение...')
        
        db.session.add(msg1)
        db.session.add(msg2)
        db.session.add(msg3)
        db.session.commit()
        
        print("✓ Добавлены тестовые сообщения")
        print("\n" + "="*50)
        print("База данных инициализирована!")
        print("="*50)
        print("\nТестовые аккаунты:")
        for user_data in users_data:
            print(f"  Тег: {user_data['tag']}")
        print(f"  Пароль для всех: {password}")
        print("="*50)

if __name__ == '__main__':
    init_database()
