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
    <h3 class="center-align">Financial Summary</h3>
    
    <!-- Summary Cards -->
    <div class="row">
        <div class="col s12 m4">
            <div class="card green lighten-1">
                <div class="card-content white-text">
                    <span class="card-title">Total Income</span>
                    <h4>AED {{ summary.total_income }}</h4>
                    <p>{{ summary.income_count }} transactions</p>
                </div>
            </div>
        </div>
        <div class="col s12 m4">
            <div class="card red lighten-1">
                <div class="card-content white-text">
                    <span class="card-title">Total Expenses</span>
                    <h4>AED {{ summary.total_expense }}</h4>
                    <p>{{ summary.expense_count }} transactions</p>
                </div>
            </div>
        </div>
        <div class="col s12 m4">
            <div class="card {% if summary.net_balance >= 0 %}blue{% else %}orange{% endif %} lighten-1">
                <div class="card-content white-text">
                    <span class="card-title">Net Balance</span>
                    <h4>AED {{ summary.net_balance }}</h4>
                    <p>{% if summary.net_balance >= 0 %}Surplus{% else %}Deficit{% endif %}</p>
                </div>
            </div>
        </div>
    </div>

    <h4>Weekly Income vs Expenses</h4>
    <div id="chart"></div>
    
    <!-- Tabs for Income and Expense Lists -->
    <div class="row">
        <div class="col s12">
            <ul class="tabs">
                <li class="tab col s2"><a href="#all-transactions">All Transactions</a></li>
                <li class="tab col s2"><a class="active" href="#income-transactions">Income</a></li>
                <li class="tab col s2"><a href="#expense-transactions">Expenses</a></li>
                <li class="tab col s3"><a href="#category-breakdown">Category Breakdown</a></li>
            </ul>
        </div>
        
        <div id="all-transactions" class="col s12">
            <h5>All Transactions</h5>
            <table class="striped">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Description</th>
                        <th>Amount</th>
                        <th>Type</th>
                        <th>Category</th>
                    </tr>
                </thead>
                <tbody>
                    {% for txn in results %}
                        <tr>
                            <td>{{ txn.date }}</td>
                            <td>{{ txn.description }}</td>
                            <td class="{% if txn.amount >= 0 %}green-text{% else %}red-text{% endif %}">
                                {{ txn.amount }}
                            </td>
                            <td>
                                <span class="chip {% if txn.type == 'Income' %}green{% else %}red{% endif %} white-text">
                                    {{ txn.type }}
                                </span>
                            </td>
                            <td>{{ txn.category }}</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div id="income-transactions" class="col s12">
            <h5>Income Transactions</h5>
            <table class="striped">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Description</th>
                        <th>Amount</th>
                        <th>Category</th>
                    </tr>
                </thead>
                <tbody>
                    {% for txn in income_transactions %}
                        <tr>
                            <td>{{ txn.date }}</td>
                            <td>{{ txn.description }}</td>
                            <td class="green-text">{{ txn.amount }}</td>
                            <td>{{ txn.category }}</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div id="expense-transactions" class="col s12">
            <h5>Expense Transactions</h5>
            <table class="striped">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Description</th>
                        <th>Amount</th>
                        <th>Category</th>
                    </tr>
                </thead>
                <tbody>
                    {% for txn in expense_transactions %}
                        <tr>
                            <td>{{ txn.date }}</td>
                            <td>{{ txn.description }}</td>
                            <td class="red-text">{{ txn.amount }}</td>
                            <td>{{ txn.category }}</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div id="category-breakdown" class="col s12">
            <h5>Category-wise Breakdown</h5>
            
            <div class="row">
                <!-- Expense Categories -->
                <div class="col s12 m6">
                    <div class="card">
                        <div class="card-content">
                            <span class="card-title red-text">Expense Categories</span>
                            <div id="expense-pie-chart"></div>
                            <table class="striped">
                                <thead>
                                    <tr>
                                        <th>Category</th>
                                        <th>Amount</th>
                                        <th>Count</th>
                                        <th>Avg</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for category, data in expense_by_category.items() %}
                                        <tr>
                                            <td>{{ category }}</td>
                                            <td class="red-text">AED {{ "%.2f"|format(data.total) }}</td>
                                            <td>{{ data.count }}</td>
                                            <td>AED {{ "%.2f"|format(data.total / data.count) }}</td>
                                        </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
                
                <!-- Income Categories -->
                <div class="col s12 m6">
                    <div class="card">
                        <div class="card-content">
                            <span class="card-title green-text">Income Categories</span>
                            <div id="income-pie-chart"></div>
                            <table class="striped">
                                <thead>
                                    <tr>
                                        <th>Category</th>
                                        <th>Amount</th>
                                        <th>Count</th>
                                        <th>Avg</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for category, data in income_by_category.items() %}
                                        <tr>
                                            <td>{{ category }}</td>
                                            <td class="green-text">AED {{ "%.2f"|format(data.total) }}</td>
                                            <td>{{ data.count }}</td>
                                            <td>AED {{ "%.2f"|format(data.total / data.count) }}</td>
                                        </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Detailed Category Transactions -->
            <div class="row">
                <div class="col s12">
                    <h6>Category Details</h6>
                    {% for category, data in expense_by_category.items() %}
                        <div class="card">
                            <div class="card-content">
                                <span class="card-title">{{ category }} - AED {{ "%.2f"|format(data.total) }} ({{ data.count }} transactions)</span>
                                <table class="striped">
                                    <thead>
                                        <tr>
                                            <th>Date</th>
                                            <th>Description</th>
                                            <th>Amount</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {% for txn in data.transactions %}
                                            <tr>
                                                <td>{{ txn.date }}</td>
                                                <td>{{ txn.description }}</td>
                                                <td class="red-text">AED {{ txn.amount }}</td>
                                            </tr>
                                        {% endfor %}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>
    
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
        },
        colors: ['#4CAF50', '#F44336', '#FF9800', '#2196F3', '#9C27B0', '#607D8B', '#795548', '#E91E63']
    };
    const chart = new ApexCharts(document.querySelector("#chart"), options);
    chart.render();
    
    // Create pie charts for category breakdown
    const expenseCategories = {{ expense_categories_json | safe }};
    const incomeCategories = {{ income_categories_json | safe }};
    
    // Expense pie chart
    if (Object.keys(expenseCategories).length > 0) {
        const expensePieOptions = {
            chart: { type: 'pie', height: 300 },
            series: Object.values(expenseCategories).map(data => data.total),
            labels: Object.keys(expenseCategories),
            colors: ['#F44336', '#E91E63', '#9C27B0', '#673AB7', '#3F51B5', '#2196F3', '#03A9F4', '#00BCD4'],
            legend: { position: 'bottom' }
        };
        const expensePieChart = new ApexCharts(document.querySelector("#expense-pie-chart"), expensePieOptions);
        expensePieChart.render();
    }
    
    // Income pie chart
    if (Object.keys(incomeCategories).length > 0) {
        const incomePieOptions = {
            chart: { type: 'pie', height: 300 },
            series: Object.values(incomeCategories).map(data => data.total),
            labels: Object.keys(incomeCategories),
            colors: ['#4CAF50', '#8BC34A', '#CDDC39', '#FFC107', '#FF9800', '#FF5722', '#795548', '#607D8B'],
            legend: { position: 'bottom' }
        };
        const incomePieChart = new ApexCharts(document.querySelector("#income-pie-chart"), incomePieOptions);
        incomePieChart.render();
    }
    
    // Initialize Materialize tabs
    document.addEventListener('DOMContentLoaded', function() {
        var elems = document.querySelectorAll('.tabs');
        var instances = M.Tabs.init(elems);
    });
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

def determine_transaction_type(amount: float, description: str) -> str:
    """Determine if transaction is income or expense based on amount and description."""
    desc = description.lower()
    
    # For credit card statements: positive amounts are expenses, negative amounts are credits/income
    if amount > 0:
        # Positive amounts are typically expenses (charges on credit card)
        return "Expense"
    else:
        # Negative amounts are typically income/credits (payments, refunds, cashbacks)
        return "Income"


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
                        transaction_type = determine_transaction_type(amount, description)
                        self.transactions.append({
                            'date': date_obj.strftime('%d/%m/%Y'),
                            'description': description.strip(),
                            'amount': round(amount, 2),
                            'type': transaction_type,
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

            # Segregate transactions by income and expense
            income_transactions = [txn for txn in transactions if txn['type'] == 'Income']
            expense_transactions = [txn for txn in transactions if txn['type'] == 'Expense']

            # Calculate totals for credit card statement
            total_income = sum(abs(txn['amount']) for txn in income_transactions)  # Credits/payments (negative amounts, show as positive)
            total_expense = sum(txn['amount'] for txn in expense_transactions)  # Charges (positive amounts)
            net_balance = total_income - total_expense  # Net payment vs charges

            # Weekly data for chart - separate income and expenses
            weekly_income = defaultdict(float)
            weekly_expense = defaultdict(lambda: defaultdict(float))
            
            for txn in transactions:
                date_obj = datetime.strptime(txn['date'], '%d/%m/%Y')
                week = date_obj.strftime('%Y-W%U')
                
                if txn['type'] == 'Income':
                    weekly_income[week] += abs(txn['amount'])  # Show credits as positive values
                else:
                    category = txn['category']
                    weekly_expense[week][category] += txn['amount']  # Expenses are already positive

            weeks = sorted(set(list(weekly_income.keys()) + list(weekly_expense.keys())))
            
            # Create series for chart
            series = []
            
            # Add income series
            income_data = [round(weekly_income.get(week, 0), 2) for week in weeks]
            series.append({'name': 'Income', 'data': income_data})
            
            # Add expense categories
            all_expense_categories = set(cat for week_data in weekly_expense.values() for cat in week_data)
            for cat in sorted(all_expense_categories):
                data = [round(weekly_expense[week].get(cat, 0), 2) for week in weeks]
                series.append({'name': f'Expense - {cat}', 'data': data})

            chart_data = {'weeks': weeks, 'series': series}
            
            # Prepare summary data
            summary = {
                'total_income': round(total_income, 2),
                'total_expense': round(total_expense, 2),
                'net_balance': round(net_balance, 2),
                'income_count': len(income_transactions),
                'expense_count': len(expense_transactions)
            }
            
            # Calculate category-wise breakdown
            expense_by_category = {}
            income_by_category = {}
            
            for txn in expense_transactions:
                category = txn['category']
                if category not in expense_by_category:
                    expense_by_category[category] = {'total': 0, 'count': 0, 'transactions': []}
                expense_by_category[category]['total'] += txn['amount']
                expense_by_category[category]['count'] += 1
                expense_by_category[category]['transactions'].append(txn)
            
            for txn in income_transactions:
                category = txn['category']
                if category not in income_by_category:
                    income_by_category[category] = {'total': 0, 'count': 0, 'transactions': []}
                income_by_category[category]['total'] += abs(txn['amount'])
                income_by_category[category]['count'] += 1
                income_by_category[category]['transactions'].append(txn)
            
            # Sort categories by total amount (descending)
            expense_by_category = dict(sorted(expense_by_category.items(), key=lambda x: x[1]['total'], reverse=True))
            income_by_category = dict(sorted(income_by_category.items(), key=lambda x: x[1]['total'], reverse=True))
            
            return render_template_string(RESULTS_HTML, 
                                        results=transactions, 
                                        chart_data=json.dumps(chart_data),
                                        summary=summary,
                                        income_transactions=income_transactions,
                                        expense_transactions=expense_transactions,
                                        expense_by_category=expense_by_category,
                                        income_by_category=income_by_category,
                                        expense_categories_json=json.dumps(expense_by_category),
                                        income_categories_json=json.dumps(income_by_category))
        finally:
            os.remove(filepath)

    return render_template_string(UPLOAD_HTML)

if __name__ == '__main__':
    app.run(port=8000, debug=True)
