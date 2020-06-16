from dotenv import load_dotenv
load_dotenv(override=True)



from app import create_app

app = create_app('dev')

