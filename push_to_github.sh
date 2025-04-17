#!/bin/bash

# Set the API Key
API_KEY="AIzaSyCulA1fueRA6AyDjjg7Yvwu4b05Z4_gyU8"

# Navigate to your project directory (Git Bash style path)
cd "/c/Users/iys32/All Programs/humanoid_ai"

# Step 1: Create a .env file with the API key
echo "GOOGLE_API_KEY=$API_KEY" > .env

# Step 2: Add .env to .gitignore if not already added
if ! grep -q "^.env$" .gitignore; then
    echo ".env" >> .gitignore
fi

echo "API key written to .env and added to .gitignore."

# Step 3: Stage, commit, and push your changes
git add .
git commit -m "Updated Final_Version.py with .env setup"
git push origin main  # Change 'main' if your branch has a different name

# Optional: Clean up .env file (uncomment to use)
# rm .env

echo "Done! Code pushed to GitHub with API key hidden."
