import ollama

def query_model(prompt, model="llama3.2:1b"):
    # Initialize Ollama client
    client = ollama.Client()

    # Define the system prompt
    system_prompt = (
     "You are SBD AI, also known as Second Brain Database AI, designed and configured by Rohan Batra "
     "for the Second Brain Database project. Your purpose is to assist in managing, organizing, and providing insights "
     "across various domains such as tasks, habits, time tracking, playlists, and networking. "
     "You are configured to integrate seamlessly with MongoDB, Python, and other tools to help users maintain "
     "a highly efficient and structured knowledge management system."
     "SBD stands for Second Brain Database"
)

    
    # Prepare the messages with the system prompt
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    # Send the request and get the response
    response = client.chat(messages=messages, model=model)
    
    # Return only the response message content
    return response.get('message', {}).get('content', 'No response content')


# Example usage
# if __name__ == "__main__":
#     prompt = "Hello, who are you? what is your name?"
#     response = query_model(prompt)
#     print(response)



