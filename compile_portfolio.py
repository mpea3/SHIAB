import sys
import subprocess
import os

def check_install():
    try:
        import markdown
    except ImportError:
        print("Installing markdown...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "markdown"])

check_install()

import markdown

def generate():
    with open('PORTFOLIO.md', 'r', encoding='utf-8') as f:
        md_text = f.read()

    # Convert markdown to HTML with TOC extension
    body_html = markdown.markdown(md_text, extensions=['extra', 'tables', 'toc'])

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SHIAB Portfolio</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;700&display=swap');

        @page {{
            size: A4;
            margin: 2.5cm 2cm;
            @bottom-right {{
                content: counter(page);
                font-family: 'Fira Code', monospace;
                font-size: 10pt;
            }}
        }}

        body {{
            font-family: 'Fira Code', monospace;
            font-size: 11pt;
            line-height: 1.6;
            color: black;
            background-color: white;
            max-width: 100%;
            margin: 0;
            padding: 0;
        }}

        h1, h2, h3, h4 {{
            color: black;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
        }}

        h1:first-of-type {{
            font-size: 28pt;
            border-bottom: none;
            padding-bottom: 0;
            margin-bottom: 0.5em;
            padding-top: 30%;
            text-align: center;
            page-break-before: avoid;
        }}

        h1:first-of-type + p, 
        h1:first-of-type + p + p {{
            text-align: center;
            font-size: 14pt;
        }}

        hr:first-of-type, hr:nth-of-type(2) {{
            page-break-after: always;
            visibility: hidden;
            height: 0;
            margin: 0;
        }}

        h1 {{
            font-size: 22pt;
            border-bottom: 2px solid black;
            padding-bottom: 10px;
            margin-bottom: 1em;
            text-align: left;
        }}

        h2 {{
            font-size: 16pt;
            border-bottom: 1px solid #aaa;
            padding-bottom: 5px;
            page-break-before: always;
        }}

        h2:first-of-type {{
            page-break-before: avoid;
            margin-top: 2em;
        }}

        h3 {{
            font-size: 13pt;
            page-break-after: avoid;
        }}

        p, li {{
            page-break-inside: avoid;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1.5em 0;
            page-break-inside: avoid;
        }}

        th, td {{
            border: 1px solid black;
            padding: 10px;
            text-align: left;
            font-size: 10pt;
        }}

        th {{
            background-color: #f7f7f7;
            font-weight: 700;
        }}

        pre, code {{
            font-family: 'Fira Code', monospace;
            background-color: #f7f7f7;
            color: black;
        }}

        code {{
            padding: 2px 4px;
            font-size: 9.5pt;
        }}

        pre {{
            padding: 12px;
            border: 1px solid #ccc;
            page-break-inside: avoid;
            white-space: pre-wrap;
            font-size: 9.5pt;
        }}
        
        pre code {{
            background-color: transparent;
            padding: 0;
        }}

        /* Make links visually look clickable */
        a {{
            color: #0000EE; /* Standard link blue */
            text-decoration: underline;
        }}
        
        a:hover {{
            color: #551A8B;
        }}

        /* TOC links */
        h2:first-of-type + ol a,
        h2:first-of-type + ul a {{
            color: #0000EE;
            text-decoration: none;
            border-bottom: 1px dotted #0000EE;
        }}
        
        hr {{
            border: 0;
            border-bottom: 1px solid #ccc;
            margin: 2em 0;
        }}
    </style>
</head>
<body>
    {body_html}
</body>
</html>
"""

    with open('PORTFOLIO.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print("PORTFOLIO.html created successfully.")

    try:
        import weasyprint
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration
        
        print("Generating PORTFOLIO.pdf...")
        font_config = FontConfiguration()
        HTML('PORTFOLIO.html').write_pdf('PORTFOLIO.pdf', font_config=font_config)
        print("Done! PORTFOLIO.pdf generated with clickable links.")
    except Exception as e:
        print(f"Notice: WeasyPrint encountered an issue. Error: {e}")

if __name__ == '__main__':
    generate()
