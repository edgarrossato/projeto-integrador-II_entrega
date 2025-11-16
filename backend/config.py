import os

class Config:
    #SQLALCHEMY_DATABASE_URI = 'sqlite:///cupcakeapp.db'
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "postgresql://admin:ABH3mSHL6RMF6vcup5GnEBkN0PmzeDt6@dpg-d4773163jp1c73bqnubg-a.oregon-postgres.render.com/cupcakeapp")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "chave_secreta")
   
