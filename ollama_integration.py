import ollama

def ollama_integration(body, subject, sender):
    response = ollama.chat(model='gemma3:1b-it-fp16', messages=[
        {'role': 'user', 'content': f"without any greeting and using numbers and bullet points summarize the email in the least amount of characters.\n subject: {subject}\n sender: {sender}\n body: {body}"}
    ])
    return response['message']['content']