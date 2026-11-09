"""Seed LAB5_ test records in the EXISTING catalogue and demonstrate API calls.
Run this only after installing the migration and starting main_new_lab5.py.
The helper is idempotent for catalog entries and versions; it does not truncate data.
"""
from __future__ import annotations
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = os.getenv('FLOWER_SHOP_API', 'http://127.0.0.1:8001').rstrip('/')

def request(method, path, params=None, payload=None):
    url = BASE + path + (('?' + urlencode(params)) if params else '')
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else None
    req = Request(url, data=data, headers={'Content-Type': 'application/json'} if data else {}, method=method)
    try:
        with urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except HTTPError as e:
        detail = e.read().decode('utf-8')
        raise RuntimeError(f'{method} {path}: HTTP {e.code}, {detail}') from e

def get(path, params=None): return request('GET',path,params=params)
def post(path, params=None, payload=None): return request('POST',path,params=params,payload=payload)

def find_category(tree, code):
    for entry in tree:
        if entry['code'] == code:
            return entry['id']
        found = find_category(entry['children'], code)
        if found is not None: return found
    return None

def category(code, name, unit_id, parent=None):
    old = find_category(get('/categories/tree'), code)
    if old is not None: return old
    return post('/categories', {'name':name,'code':code,'base_unit_id':unit_id,
                                 **({'parent_id':parent} if parent else {})})['id_category']

def unit(short_name, full_name, integer):
    for entry in get('/units'):
        if entry['short_name'] == short_name and bool(entry['is_integer_only']) == integer:
            return entry['id_unit']
    return post('/units',{'name':full_name,'short_name':short_name,'is_integer_only':str(integer).lower()})['id_unit']

def product(code, name, cat_id, unit_id, price):
    found = get('/products/search', {'q':code})['items']
    for p in found:
        if p['code'] == code: return p['id_product']
    return post('/products', {'name':name,'code':code,'category_id':cat_id,
                              'unit_id':unit_id,'price':price})['id_product']

def first_version(product_id, items, **kwargs):
    versions = get(f'/bom/products/{product_id}/versions')
    if versions:
        return versions[0]['id_spec_version']
    return post(f'/bom/products/{product_id}/versions', payload={'items':items, **kwargs})['id_spec_version']

def line(product_id, quantity): return {'component_product_id':product_id,'quantity':quantity}

def modification(code, name, version_id, changes):
    old=get('/products/search',{'q':code})['items']
    for p in old:
        if p['code']==code:
            versions=get(f"/bom/products/{p['id_product']}/versions")
            if versions: return versions[0]['id_spec_version']
    return post('/bom/modifications',payload={'code':code,'name':name,'base_version_id':version_id,
                                             'items':changes})['version']['id_spec_version']

def make_enum_param(code, name, values):
    for p in get('/parameters'):
        if p['code'] == code:
            pid=p['id_parameter']
            break
    else:
        # Prefer enum type of an existing known parameter; in the original app it is type 3.
        enum_type_id=next((p['id_param_type'] for p in get('/parameters') if p['code'] in ('COLOR','THEME')),3)
        p=post('/parameters',{'name':name,'short_name':code.lower(),'code':code,
                              'id_param_type':enum_type_id})
        pid=p['id_parameter']
    enum_code=code+'_VALUES'
    en=next((e for e in get('/enums') if e['code']==enum_code),None)
    if en is None:
        en=post('/enums',{'name':name+' values','code':enum_code,'param_id':pid})
    existing={e['item_code'] for e in get(f"/enums/{en['id_enum']}/items")}
    for val in values:
        if val not in existing:
            post('/enum-items',{'id_enum':en['id_enum'],'item_name':val,'item_code':val})
    return pid

def main():
    print('API:',BASE)
    piece=unit('шт.','штука',True)
    meter=unit('м','метр',False)
    top=category('LAB5_DEMO','Лабораторная работа №5',piece)
    flowers=category('LAB5_FLOWERS','Тестовые цветы',piece,top)
    packages=category('LAB5_PACKAGES','Тестовая упаковка',piece,top)
    assemblies=category('LAB5_ASSEMBLIES','Тестовые сборки',piece,top)
    rose=product('LAB5_ROSE','Роза (тест)',flowers,piece,10)
    green=product('LAB5_GREEN','Зелень (тест)',flowers,piece,5)
    chrys=product('LAB5_CHRYS','Хризантема (тест)',flowers,piece,7)
    paper=product('LAB5_PAPER','Упаковка (тест)',packages,piece,3)
    ribbon=product('LAB5_RIBBON','Лента (тест)',packages,meter,2)
    sweets=product('LAB5_SWEETS','Конфеты (тест)',packages,piece,30)
    card=product('LAB5_CARD','Открытка (тест)',packages,piece,10)
    mono=product('LAB5_MONO','Монобукет (тест)',assemblies,piece,80)
    spring=product('LAB5_SPRING','Весенний (тест)',assemblies,piece,150)
    gift=product('LAB5_GIFT','Подарочный набор (тест)',assemblies,piece,200)

    mono_v=first_version(mono,[line(rose,5),line(green,1)])
    spring_v=first_version(spring,[line(mono,1),line(chrys,3),line(green,2),line(paper,1),line(ribbon,1)])
    summary=post('/bom/expand',payload={'version_id':spring_v,'quantity':2})['leaf_summary']
    assert {entry['product_id']:entry['quantity'] for entry in summary}=={
        rose:10,chrys:6,green:6,paper:2,ribbon:2}
    print('\n[Example 1] nested BOM, quantity 2:')
    for entry in summary: print(' -',entry['name'],entry['quantity'],entry['unit'])

    gift_v=first_version(gift,[line(mono,1),line(sweets,1),line(paper,1)])
    items=get(f'/bom/versions/{gift_v}')['items']
    sweet_item=next(item['id'] for item in items if item['position_num']==2)
    a_v=modification('LAB5_MOD_A','Набор без конфет (тест)',gift_v,
                     [{'action':'exclude','target_item_id':sweet_item}])
    b_v=modification('LAB5_MOD_B','Набор с открыткой без конфет (тест)',a_v,[line(card,1)])
    b_need=post('/bom/expand',payload={'version_id':b_v})['leaf_summary']
    product_ids={entry['product_id'] for entry in b_need}
    assert sweets not in product_ids and card in product_ids
    print('\n[Example 2] modification B:')
    for entry in b_need: print(' -',entry['name'],entry['quantity'],entry['unit'])

    # Configuration; use two enumerated parameters in the same global catalog.
    size_code='LAB5_SIZE'
    box_code='LAB5_BOX_SIZE'
    make_enum_param(size_code,'Размер букета (тест)', ['S','M','L'])
    make_enum_param(box_code,'Коробка букета (тест)', ['small','large'])
    configurable=product('LAB5_CONFIG','Букет-конфигуратор (тест)',assemblies,piece,100)
    c_v=first_version(configurable,[line(rose,5)],
        config_params=[{'parameter_code':size_code,'is_required':True},
                       {'parameter_code':box_code,'is_required':True}],
        rules=[
            {'rule_name':'Размер M','action':'quantity','target_position_num':1,'result_quantity':9,
             'conditions':[{'parameter_code':size_code,'value_text':'M'}]},
            {'rule_name':'Размер L','action':'quantity','target_position_num':1,'result_quantity':15,
             'conditions':[{'parameter_code':size_code,'value_text':'L'}]},
            {'rule_name':'Большому букету нужна большая коробка','action':'forbid',
             'message':'Для размера L маленькая коробка запрещена',
             'conditions':[{'parameter_code':size_code,'value_text':'L','condition_num':1},
                           {'parameter_code':box_code,'value_text':'small','condition_num':2}]}
        ])
    good=post('/bom/expand',payload={'version_id':c_v,'params':{size_code:'L',box_code:'large'}})
    assert {v['product_id']:v['quantity'] for v in good['leaf_summary']}=={rose:15}
    saved=post('/bom/variants',payload={'version_id':c_v,'name':'Конфигурация L большая коробка',
                                       'params':{size_code:'L',box_code:'large'}})
    print('\n[Example 3] configured variant:',saved['id_variant'],good['leaf_summary'])
    print('Completed. Catalog demo entries start with LAB5_. No orders or HTML edits.')

if __name__=='__main__':
    try: main()
    except (RuntimeError,URLError) as e:
        raise SystemExit(str(e))
