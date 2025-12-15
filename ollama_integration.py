import ollama

def ollama_integration(body, subject, sender):
    response = ollama.chat(model='sum', messages=[
        {'role': 'user', 'content': f"sender: {sender}\nsubject: {subject}\nbody: {body}"}
    ])
    return response['message']['content']