import ollama

def ollama_integration(body, subject, sender):
    response = ollama.chat(model='sum', messages=[
        {'role': 'user', 'content': f"without any greeting, summarize the email in the least amount of characters.\n subject: {subject}\n sender: {sender}\n body: {body}"}
    ])
    return response['message']['content']