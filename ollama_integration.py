import ollama

def ollama_integration(body, subject, sender):
    response = ollama.chat(model='gemma3:1b', messages=[
        {'role': 'user', 'content': f"without any greeting and using numbers and bullet points summarize the email in the least amount of characters.\n subject: {subject}\n sender: {sender}\n body: {body}"}
    ])
    return response['message']['content']

print(ollama_integration('''
Google
You allowed Pegion - Email Summarizer access to some of your Google Account data
	cyberwarrior911@gmail.com

If you didn’t allow Pegion - Email Summarizer access to some of your Google Account data, someone else may be trying to access your Google Account data.

Take a moment now to check your account activity and secure your account.

Check activity
To make changes at any time to the access that Pegion - Email Summarizer has to your data, go to your Google Account
You can also see security activity at
https://myaccount.google.com/notifications
Show quoted text
''', "a new sign in to your google account", "google-noreply@gmail.com"))