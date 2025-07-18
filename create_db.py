from chat_app import app, db
from chat_app.models import User

with app.app_context():
    db.create_all()
    print("Tables created successfully!")

    bot_user = User.query.filter_by(username="ChatBot").first()
    if not bot_user:
        bot_user = User(username="ChatBot")
        # Set a dummy password hash (you can generate hash for e.g. 'botpassword')
        bot_user.set_password("botpassword")
        db.session.add(bot_user)
        db.session.commit()
        print("ChatBot user created.")
    else:
        print("ChatBot user already exists.")
