from flask import Flask, request, render_template_string
import os
from werkzeug.utils import secure_filename
import pdfplumber
from datetime import datetime
import re
from typing import Dict, List, Any
from collections import defaultdict
import json

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

UPLOAD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>ENBD Statement Parser</title>
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0/css/materialize.min.css">
</head>
<body>
<div class="container">
    <h3 class="center-align">ENBD Statement Parser</h3>
    <form method="post" enctype="multipart/form-data">
        <div class="file-field input-field">
            <div class="btn">
                <span>File</span>
                <input type="file" name="file" accept=".pdf">
            </div>
            <div class="file-path-wrapper">
                <input class="file-path validate" type="text" placeholder="Upload PDF file">
            </div>
        </div>
        <div class="input-field">
            <input id="password" type="password" name="password" class="validate">
            <label for="password">Password (Optional)</label>
        </div>
        <div class="center-align">
            <button class="btn waves-effect waves-light" type="submit">
                Parse PDF
                <i class="material-icons right">send</i>
            </button>
        </div>
    </form>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0/js/materialize.min.js"></script>
</body>
</html>
'''

RESULTS_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Parsing Results</title>
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0/css/materialize.min.css">
    <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
</head>
<body>
<div class="container">
    <h3 class="center-align">Weekly Spending by Category</h3>
    <div id="chart"></div>
    <h4>Transaction List</h4>
    <table class="striped">
        <thead>
            <tr>
                {% for key in results[0].keys() %}
                    <th>{{ key }}</th>
                {% endfor %}
            </tr>
        </thead>
        <tbody>
            {% for row in results %}
                <tr>
                    {% for value in row.values() %}
                        <td>{{ value }}</td>
                    {% endfor %}
                </tr>
            {% endfor %}
        </tbody>
    </table>
    <div class="center-align" style="margin: 20px 0;">
        <a href="/" class="btn">Parse Another File</a>
    </div>
</div>
<script>
    const chartData = {{ chart_data | safe }};
    const options = {
        chart: { type: 'area', height: 400, zoom: { enabled: true } },
        dataLabels: { enabled: false },
        stroke: { curve: 'smooth' },
        series: chartData.series,
        xaxis: {
            categories: chartData.weeks,
            title: { text: 'Week' }
        },
        yaxis: {
            title: { text: 'Amount (AED)' }
        }
    };
    const chart = new ApexCharts(document.querySelector("#chart"), options);
    chart.render();
</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0/js/materialize.min.js"></script>
</body>
</html>
'''

def categorize(description: str) -> str:
    desc = description.lower()
    if any(x in desc for x in ['restaurant', 'talabat', 'kfc', 'hardees', 'soho garden', 'gazebo', 'tasty pizza', 
                              'pulao', 'shake', 'cafe', 'noon minutes', 'wakha', 'meraki', 'hot n spicy', 'pak darbar',
                              'apna kabab', 'mcdonalds', 'carrefour food', 'fillicafe']):
        return "Food & Dining"
    if any(x in desc for x in ['taxi', 'careem', 'zo feur', 'dubai taxi', 'emarat', 'epcco', 'enoc', 
                              'car rental', 'hala']):
        return "Transport" 
    if any(x in desc for x in ['noon.com', 'carrefour', 'home centre', 'pakistan supermarket', 'supermarket',
                              'minutes', 'apple.com', 'itunes', 'openai', 'netflix', 'cursor']):
        return "Shopping"
    if any(x in desc for x in ['platiniumlist', 'reel entertainment', 'soho garden', 'expedia', 'leisure',
                              'mmall', 'smart dubai government']):
        return "Entertainment"
    if any(x in desc for x in ['dewa', 'electricity', 'smart dubai', 'etisalat', 'du', 'swyp']):
        return "Utilities"
    if any(x in desc for x in ['salon', 'barber', 'dry clean', 'laundry', 'spa']):
        return "Personal Care"
    if any(x in desc for x in ['openai', 'netflix', 'whoop', 'cursor', 'apple', 'itunes', 'chatgpt']):
        return "Subscription/Online"
    return "Others"


class ENBDStatementParser:
    def __init__(self, pdf_path: str, password: str = None):
        self.pdf_path = pdf_path
        self.password = password
        self.transactions = []
        
    def extract_text(self) -> List[str]:
        with pdfplumber.open(self.pdf_path, password=self.password) as pdf:
            return [page.extract_text() for page in pdf.pages if page.extract_text()]

    def parse_transactions(self, pages: List[str]) -> None:
        for page in pages:
            for line in page.split('\n'):
                match = re.search(r'(\d{2}/\d{2}/\d{4}).+?([A-Z].+?)\s+([-\d,.]+)$', line)
                if match:
                    date_str, description, amount_str = match.groups()
                    try:
                        date_obj = datetime.strptime(date_str, '%d/%m/%Y')
                        amount = float(amount_str.replace(',', ''))
                        self.transactions.append({
                            'date': date_obj.strftime('%d/%m/%Y'),
                            'description': description.strip(),
                            'amount': round(amount, 2),
                            'category': categorize(description)
                        })
                    except:
                        continue

    def parse(self) -> List[Dict[str, Any]]:
        pages = self.extract_text()
        self.parse_transactions(pages)
        return self.transactions

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part'
        file = request.files['file']
        password = request.form.get('password', '')
        if file.filename == '':
            return 'No selected file'
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(filepath)

        try:
            parser = ENBDStatementParser(filepath, password)
            transactions = parser.parse()

            weekly_data = defaultdict(lambda: defaultdict(float))
            for txn in transactions:
                date_obj = datetime.strptime(txn['date'], '%d/%m/%Y')
                week = date_obj.strftime('%Y-W%U')
                category = txn['category']
                weekly_data[week][category] += abs(txn['amount'])

            weeks = sorted(weekly_data.keys())
            all_categories = set(cat for week_data in weekly_data.values() for cat in week_data)
            series = []
            for cat in sorted(all_categories):
                data = [round(weekly_data[week].get(cat, 0), 2) for week in weeks]
                series.append({'name': cat, 'data': data})

            chart_data = {'weeks': weeks, 'series': series}
            return render_template_string(RESULTS_HTML, results=transactions, chart_data=json.dumps(chart_data))
        finally:
            os.remove(filepath)

    return render_template_string(UPLOAD_HTML)

if __name__ == '__main__':
    app.run(port=8000, debug=True)
