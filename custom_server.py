#!/usr/bin/env python3
import http.server
import socketserver
import os
import urllib.parse

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Decode the path
        path = urllib.parse.unquote(path)
        # Remove leading slash
        if path.startswith('/'):
            path = path[1:]
        # Get the full path
        full_path = os.path.join(os.getcwd(), path)
        # Normalize the path
        full_path = os.path.normpath(full_path)
        print(f"Requested: {path} -> Resolved: {full_path} -> Exists: {os.path.exists(full_path)}")
        return full_path

if __name__ == '__main__':
    PORT = 8000
    os.chdir('.')  # Ensure we're in the project root
    print(f"Starting server on port {PORT}")
    print(f"Server root: {os.getcwd()}")
    print(f"Instagram folder exists: {os.path.exists('Instagram')}")
    
    with socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
        print(f"Server running at http://localhost:{PORT}/")
        httpd.serve_forever()
