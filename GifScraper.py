from requests import get
from bs4 import BeautifulSoup
from random import choice

def fetch_random_gif():
    # URL of the page containing GIFs (example: trending GIFs on Giphy)
    url = "https://giphy.com"
    
    # Send a GET request to fetch the content of the page
    response = get(url)
    
    # Check if the request was successful
    if response.status_code == 200:
        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all image tags with GIFs
        gifs = soup.find_all('img', {'src': True})
        
        # Filter out only valid GIF URLs (usually ending with .gif)
        gif_urls = [gif['src'] for gif in gifs if gif['src'].endswith('.gif')]
        
        # Select a random GIF URL
        if gif_urls:
            random_gif = choice(gif_urls)
            return random_gif
        else:
            return "No gifs today :("
    else:
        return "Failed to get you a gif :(."

# Example usage
if __name__ == "__main__":
    [print(fetch_random_gif()) for i in range(10)]
