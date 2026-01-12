import http.server
import socketserver
import os

# Change to the script directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

PORT = 8000

Handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"✅ Server running at http://localhost:{PORT}/")
    print(f"📂 Open: http://localhost:{PORT}/companies_viewer.html")
    print("\nPress Ctrl+C to stop the server")
    httpd.serve_forever()
