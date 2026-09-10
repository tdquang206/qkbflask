"""Drug routes with real templates/CSRF and entirely in-memory databases."""

import importlib.util
import sys
import types
from html.parser import HTMLParser
from pathlib import Path
from unicodedata import normalize

import pytest
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from utils.drug_values import drug_stock_details

ROOT = Path(__file__).resolve().parents[1]


class FormParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.fields = {}
        self.cost_buttons = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and 'name' in attrs:
            self.fields[attrs['name']] = attrs.get('value', '')
        if tag == 'button' and 'data-cost' in attrs:
            self.cost_buttons.append(attrs['data-cost'])


@pytest.fixture
def drug_app(monkeypatch):
    database = TinyDB(storage=MemoryStorage)
    shared = types.ModuleType('shared_db')
    shared.drugs_table = database.table('drugs')
    shared.patients_table = database.table('patients')
    purchase_module = types.ModuleType('routes.mua_thuoc')
    purchase_module.purchases_table = database.table('purchases')
    monkeypatch.setitem(sys.modules, 'shared_db', shared)
    monkeypatch.setitem(sys.modules, 'routes.mua_thuoc', purchase_module)

    spec = importlib.util.spec_from_file_location('isolated_drug_routes', ROOT / 'routes/drugs.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'TinyDB', lambda *args, **kwargs: database)
    app = Flask(__name__, template_folder=str(ROOT / 'templates'),
                static_folder=str(ROOT / 'static'))
    app.config.update(TESTING=True, SECRET_KEY='synthetic-test-secret')
    CSRFProtect(app)
    app.register_blueprint(module.drugs_bp)
    # Keep the real base template without importing production startup/databases.
    for endpoint in ('settings.discord_settings', 'settings.departments_settings',
                     'settings.services_management', 'settings.manage_template', 'auth.login'):
        app.add_url_rule('/stub/' + endpoint, endpoint, lambda: '')
    app.jinja_env.globals['current_user'] = types.SimpleNamespace(is_authenticated=False)
    drug_id = shared.drugs_table.insert({
        'sku': 'TEST', 'name': 'Thuốc 10mg', 'sell_price': 10000.0,
        'buy_price': 7850.0, 'quantity': 1200, 'inventory': 1200,
        'legacy_extra': 'preserve me',
    })
    yield app.test_client(), database, drug_id
    database.close()


def edit_form(client, drug_id):
    response = client.get(f'/edit_drug/{drug_id}')
    assert response.status_code == 200
    return FormParser(response.get_data(as_text=True))


def test_repeated_save_preserves_prices_and_legacy_fields(drug_app):
    client, db, drug_id = drug_app
    for _ in range(3):
        fields = edit_form(client, drug_id).fields
        response = client.post(f'/edit_drug/{drug_id}', data=fields)
        assert response.status_code == 302
        saved = db.table('drugs').get(doc_id=drug_id)
        assert saved['sell_price'] == 10000.0
        assert saved['buy_price'] == 7850.0
        assert saved['inventory'] == 1200
        assert saved['legacy_extra'] == 'preserve me'


def test_change_both_prices_then_save_again(drug_app):
    client, db, drug_id = drug_app
    fields = edit_form(client, drug_id).fields
    fields.update(sell_price='12500.50', buy_price='8000.25')
    assert client.post(f'/edit_drug/{drug_id}', data=fields).status_code == 302
    fields = edit_form(client, drug_id).fields
    assert client.post(f'/edit_drug/{drug_id}', data=fields).status_code == 302
    saved = db.table('drugs').get(doc_id=drug_id)
    assert (saved['sell_price'], saved['buy_price']) == (12500.50, 8000.25)


@pytest.mark.parametrize('field,value', [
    ('sell_price', 'nan'), ('buy_price', 'inf'), ('buy_price', '1e999'),
    ('sell_price', '-1'), ('buy_price', 'abc'), ('buy_price', ''),
    ('quantity', '2.5'), ('inventory', '-1'), ('name', '   '),
])
def test_invalid_update_is_atomic_and_shows_error(drug_app, field, value):
    client, db, drug_id = drug_app
    fields = edit_form(client, drug_id).fields
    before = dict(db.table('drugs').get(doc_id=drug_id))
    fields.update(name='Changed Name', sell_price='12345.67')
    fields[field] = value
    response = client.post(f'/edit_drug/{drug_id}', data=fields)
    assert response.status_code == 400
    assert 'Drug was not updated.' in response.get_data(as_text=True)
    assert dict(db.table('drugs').get(doc_id=drug_id)) == before


def test_create_decimal_prices_and_invalid_create(drug_app):
    client, db, _ = drug_app
    response = client.get('/drugs')
    fields = FormParser(response.get_data(as_text=True)).fields
    fields.update(sku='NEW', name='New Drug', sell_price='10000.50',
                  buy_price='7850.25', quantity='30')
    assert client.post('/drugs', data=fields).status_code == 302
    saved = db.table('drugs').all()[-1]
    assert (saved['sell_price'], saved['buy_price']) == (10000.50, 7850.25)
    assert saved['inventory'] == ''
    fields['sell_price'] = 'bad'
    response = client.post('/drugs', data=fields)
    assert response.status_code == 400
    assert 'Drug was not created.' in response.get_data(as_text=True)
    assert 'modal is-active' in response.get_data(as_text=True)
    assert len(db.table('drugs')) == 2


def test_csrf_and_missing_record(drug_app):
    client, db, drug_id = drug_app
    assert client.post(f'/edit_drug/{drug_id}', data={'name': 'blocked'}).status_code == 400
    assert client.get('/edit_drug/999').status_code == 404
    fields = edit_form(client, drug_id).fields
    assert client.post('/edit_drug/999', data=fields).status_code == 404


def test_history_ppu_and_cost_selection_save(drug_app):
    client, db, drug_id = drug_app
    db.table('purchases').insert({'date_buy': '2025-01-01', 'drugs': [
        {'name': 'Thuốc 10mg', 'quantity': 3, 'buy_price': 10000},
    ]})
    db.table('purchases').insert({'date_buy': '2026-09-07', 'drugs': [
        {'name': 'Thuốc 10mg', 'quantity': 900, 'buy_price': 7050000, 'ppu': 7850},
        {'name': 'Thuốc 100mg', 'quantity': 100, 'buy_price': 100000},
    ]})
    db.table('patients').insert({'exams': [
        {'exam_date': '2020-01-01', 'paid_status': False,
         'drugs': [{'name': 'Thuốc 10mg', 'quantity': '600'}]},
    ]})
    form = edit_form(client, drug_id)
    assert form.cost_buttons == ['7850.00', '3333.33']
    assert db.table('drugs').get(doc_id=drug_id)['buy_price'] == 7850
    form.fields['buy_price'] = form.cost_buttons[1]
    assert client.post(f'/edit_drug/{drug_id}', data=form.fields).status_code == 302
    saved = db.table('drugs').get(doc_id=drug_id)
    assert saved['buy_price'] == 3333.33
    assert saved['inventory'] == 1200
    html = client.get(f'/edit_drug/{drug_id}').get_data(as_text=True)
    assert '<strong>903</strong>' in html
    assert '<strong>600</strong>' in html
    assert '<strong>303</strong>' in html


def test_all_time_stock_normalization_invalid_quantities_and_negative_balance():
    name = 'Thuốc 10mg'
    purchases = [{'date_buy': '2024-01-01', 'drugs': [
        {'name': normalize('NFD', name.upper()), 'quantity': '10.0', 'buy_price': 100},
        {'name': name, 'quantity': 0, 'buy_price': 100},
        {'name': name, 'quantity': 'broken', 'ppu': 'nan'},
        {'name': 'Thuốc 100mg', 'quantity': 999},
    ]}]
    patients = [{'exams': [
        {'paid_status': False, 'drugs': [{'name': '  ' + name + ' ', 'quantity': '12'}]},
        {'exam_date': '2020-01-01', 'drugs': [{'name': name, 'quantity': None}]},
        {'drugs': [{'name': 'Thuốc 100mg', 'quantity': 999}]},
    ]}]
    history, stock = drug_stock_details(name, purchases, patients)
    assert stock == {'bought': 10, 'sold': 12, 'inventory': -2, 'skipped': 2}
    assert [row['ppu'] for row in history] == [10.0, None, None]
    assert drug_stock_details(name, [], [])[1]['inventory'] == 0
