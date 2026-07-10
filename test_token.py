from services.broker.token import get_access_token

code = input("Enter authorization code:\n")

token = get_access_token(code)

print(token)