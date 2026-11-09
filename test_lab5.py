"""Automated SQLite smoke tests for the Lab 5 engine; no PostgreSQL required."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Numeric, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool
from bom_lab5 import install_bom

@pytest.fixture()
def env():
    Base = declarative_base()
    class Category(Base):
        __tablename__='categories'
        id_category=Column(Integer, primary_key=True)
        name=Column(String(200))
        code=Column(String(50))
        parent_id=Column(Integer, ForeignKey('categories.id_category'))
    class Unit(Base):
        __tablename__='units'
        id_unit=Column(Integer, primary_key=True)
        name=Column(String(100))
        short_name=Column(String(20))
        is_integer_only=Column(Boolean, default=False)
    class Product(Base):
        __tablename__='products'
        id_product=Column(Integer, primary_key=True)
        name=Column(String(200))
        code=Column(String(50))
        category_id=Column(Integer, ForeignKey('categories.id_category'))
        unit_id=Column(Integer, ForeignKey('units.id_unit'))
        price=Column(Integer)
        is_composite=Column(Boolean, default=False)
    class ParamType(Base):
        __tablename__='param_type'
        id_param_type=Column(Integer, primary_key=True)
        sys_code=Column(String(20))
    class Parameter(Base):
        __tablename__='parameters'
        id_parameter=Column(Integer, primary_key=True)
        name=Column(String(100))
        code=Column(String(50))
        id_param_type=Column(Integer, ForeignKey('param_type.id_param_type'))
        min_value=Column(Numeric)
        max_value=Column(Numeric)
    class EnumValue(Base):
        __tablename__='enum_values'
        id_enum_value=Column(Integer, primary_key=True)
        parameter_id=Column(Integer, ForeignKey('parameters.id_parameter'))
        value_name=Column(String(100))
        value_code=Column(String(50))

    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    SessionLocal=sessionmaker(bind=engine)
    def db_dep():
        with SessionLocal() as session:
            yield session
    app=FastAPI()
    models=install_bom(app, Base, db_dep, Product, Category, Unit, Parameter, ParamType, EnumValue)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add_all([Unit(id_unit=1,name='piece',short_name='шт.',is_integer_only=True),
                    Unit(id_unit=2,name='meter',short_name='м',is_integer_only=False),
                    Category(id_category=1,name='All',code='ALL'),
                    Category(id_category=2,name='Flowers',code='FLOWERS',parent_id=1),
                    Category(id_category=3,name='Packaging',code='PACK',parent_id=1),
                    Category(id_category=4,name='Bouquets',code='BOUQ',parent_id=1),
                    ParamType(id_param_type=1,sys_code='enum'),
                    ParamType(id_param_type=2,sys_code='integer')])
        db.add_all([
            Product(id_product=1,name='Роза',code='ROSE',category_id=2,unit_id=1,price=10),
            Product(id_product=2,name='Зелень',code='GREEN',category_id=2,unit_id=1,price=4),
            Product(id_product=3,name='Хризантема',code='CHRYS',category_id=2,unit_id=1,price=5),
            Product(id_product=4,name='Лист упаковки',code='PAPER',category_id=3,unit_id=1,price=3),
            Product(id_product=5,name='Лента',code='RIBBON',category_id=3,unit_id=2,price=1),
            Product(id_product=6,name='Монобукет',code='MONO',category_id=4,unit_id=1,price=100),
            Product(id_product=7,name='Букет Весенний',code='SPRING',category_id=4,unit_id=1,price=200),
            Product(id_product=8,name='Конфеты',code='SWEETS',category_id=3,unit_id=1,price=50),
            Product(id_product=9,name='Набор',code='GIFT',category_id=4,unit_id=1,price=250),
            Product(id_product=10,name='Открытка',code='CARD',category_id=3,unit_id=1,price=20),
            Product(id_product=11,name='Большая коробка',code='BOX',category_id=3,unit_id=1,price=15)])
        db.add_all([Parameter(id_parameter=1,name='Размер',code='SIZE',id_param_type=1),
                    Parameter(id_parameter=2,name='Коробка',code='BOX_SIZE',id_param_type=1)])
        db.add_all([EnumValue(parameter_id=1,value_code=c,value_name=c) for c in ['S','M','L']])
        db.add_all([EnumValue(parameter_id=2,value_code=c,value_name=c) for c in ['small','large']])
        db.commit()
    yield TestClient(app), models, SessionLocal
    engine.dispose()

def post(client,url,data):
    r=client.post(url,json=data)
    assert r.status_code==200, f'{url} => {r.status_code}: {r.text}'
    return r.json()

def add(client,product,lines,**kw):
    return post(client,f'/bom/products/{product}/versions',{'items':lines,**kw})

def line(product,quantity,**kw):
    return {'component_product_id':product,'quantity':quantity,**kw}

def create_mono(client):
    return add(client,6,[line(1,5),line(2,1)])['id_spec_version']

def create_spring(client):
    create_mono(client)
    return add(client,7,[line(6,1),line(3,3),line(2,2),line(4,1),line(5,1)])['id_spec_version']

def summary_map(body):
    return {x['product_id']: x['quantity'] for x in body['leaf_summary']}

def test_nested_bom_sum_repeated_and_category_filter(env):
    c,_,_=env
    spring=create_spring(c)
    data=post(c,'/bom/expand',{'version_id':spring,'quantity':2})
    assert summary_map(data)=={1:10,2:6,3:6,4:2,5:2}
    assert data['tree']['children'][0]['children'][0]['name']=='Роза'
    filtered=post(c,'/bom/expand',{'version_id':spring,'quantity':2,'category_id':2})
    assert summary_map(filtered)=={1:10,2:6,3:6}
    assert len(filtered['tree']['children'])==5

def test_modification_chain_and_unchanged_base(env):
    c,_,_=env
    mono=create_mono(c)
    base=add(c,9,[line(6,1),line(8,1),line(4,1)])['id_spec_version']
    items=c.get(f'/bom/versions/{base}').json()['items']
    sweet_id=next(x['id'] for x in items if x['position_num']==2)
    a=post(c,'/bom/modifications',{'name':'Без конфет','code':'MOD_A','base_version_id':base,
                                   'items':[{'action':'exclude','target_item_id':sweet_id}]})
    b=post(c,'/bom/modifications',{'name':'Без конфет с открыткой','code':'MOD_B',
                                   'base_version_id':a['version']['id_spec_version'],
                                   'items':[line(10,1)]})
    bs=summary_map(post(c,'/bom/expand',{'version_id':b['version']['id_spec_version']}))
    assert 8 not in bs and bs[10]==1 and bs[1]==5
    assert summary_map(post(c,'/bom/expand',{'version_id':base}))[8]==1
    assert 10 not in summary_map(post(c,'/bom/expand',{'version_id':a['version']['id_spec_version']}))

def test_saved_variant_immutable_after_base_version_change(env):
    c,_,_=env
    original=add(c,9,[line(8,1)])['id_spec_version']
    variant=post(c,'/bom/variants',{'name':'Исторический набор','version_id':original})
    later=add(c,9,[line(10,1)],comment='Заменили конфеты открыткой')['id_spec_version']
    assert summary_map(c.get(f"/bom/variants/{variant['id_variant']}").json())=={8:1}
    assert summary_map(post(c,'/bom/expand',{'version_id':later}))=={10:1}
    assert len(c.get('/bom/products/9/history').json())==2

def test_negative_fraction_and_cycle_rejected_without_partial_commit(env):
    c,m,S=env
    assert c.post('/bom/products/6/versions',json={'items':[line(1,-1)]}).status_code==400
    assert c.get('/bom/products/6/versions').json()==[]
    assert c.post('/bom/products/6/versions',json={'items':[line(1,0.5)]}).status_code==400
    assert c.post('/bom/products/6/versions',json={'items':[line(6,1)]}).status_code==400
    assert c.get('/bom/products/6/versions').json()==[]
    mono=create_mono(c)
    assert c.post('/bom/expand',json={'version_id':mono,'quantity':0.5}).status_code==400

def test_config_rules_and_forbidden_combination(env):
    c,_,_=env
    ver=add(c,6,[line(1,5),line(2,1)],
            config_params=[{'parameter_code':'SIZE','is_required':True},
                           {'parameter_code':'BOX_SIZE','is_required':True}],
            rules=[
                {'rule_name':'Size M','action':'quantity','target_position_num':1,'result_quantity':9,
                 'conditions':[{'parameter_code':'SIZE','value_text':'M'}]},
                {'rule_name':'Size L','action':'quantity','target_position_num':1,'result_quantity':15,
                 'conditions':[{'parameter_code':'SIZE','value_text':'L'}]},
                {'rule_name':'No small box with L','action':'forbid',
                 'message':'Для L нельзя маленькую коробку',
                 'conditions':[{'parameter_code':'SIZE','value_text':'L','condition_num':1},
                               {'parameter_code':'BOX_SIZE','value_text':'small','condition_num':2}]},
            ])['id_spec_version']
    selected=post(c,'/bom/expand',{'version_id':ver,'params':{'SIZE':'L','BOX_SIZE':'large'}})
    assert summary_map(selected)=={1:15,2:1}
    error=c.post('/bom/expand',json={'version_id':ver,'params':{'SIZE':'L','BOX_SIZE':'small'}})
    assert error.status_code==400 and 'маленькую' in error.text
    assert c.post('/bom/expand',json={'version_id':ver,'params':{'SIZE':'X','BOX_SIZE':'large'}}).status_code==400
    assert c.post('/bom/expand',json={'version_id':ver,'params':{'BOX_SIZE':'large'}}).status_code==400

def test_parameter_link_to_nested_bouquet_and_conflict_rules(env):
    c,_,_=env
    mono=add(c,6,[line(1,5)], config_params=[{'parameter_code':'SIZE','is_required':True}],
            rules=[{'rule_name':'M=9','action':'quantity','target_position_num':1,'result_quantity':9,
                    'conditions':[{'parameter_code':'SIZE','value_text':'M'}]}])['id_spec_version']
    gift=add(c,9,[line(6,1)],config_params=[{'parameter_code':'SIZE','is_required':True}],
             param_links=[{'child_position_num':1,'source_parameter_code':'SIZE','target_parameter_code':'SIZE'}])['id_spec_version']
    result=post(c,'/bom/expand',{'version_id':gift,'params':{'SIZE':'M'}})
    assert summary_map(result)=={1:9}
    one=post(c,'/bom/variants',{'version_id':gift,'name':'Выбранный размер M','params':{'SIZE':'M'}})
    assert summary_map(c.get(f"/bom/variants/{one['id_variant']}").json())=={1:9}
    assert c.post('/bom/expand',json={'version_id':gift,'params':{'SIZE':'invalid'}}).status_code==400

def test_rule_conflict_rejected(env):
    c,_,_=env
    v=add(c,6,[line(1,5)],config_params=[{'parameter_code':'SIZE','is_required':True}],
          rules=[{'rule_name':f'R{i}','action':'quantity','target_position_num':1,'result_quantity':val,
                  'conditions':[{'parameter_code':'SIZE','value_text':'M'}]} for i,val in [(1,8),(2,9)]])['id_spec_version']
    result=c.post('/bom/expand',json={'version_id':v,'params':{'SIZE':'M'}})
    assert result.status_code==400 and 'Конфликт' in result.text

def test_fractional_delta_rejected_and_category_assembly_filter(env):
    c,_,_=env
    mono=create_mono(c)
    item_id=c.get(f'/bom/versions/{mono}').json()['items'][0]['id']
    # Fractional rose count in a modification must fail at save time.
    resp=c.post('/bom/modifications',json={'name':'Половина розы','code':'HALF','base_version_id':mono,
        'items':[{'action':'quantity','target_item_id':item_id,'quantity':0.5}]})
    assert resp.status_code==400
    assert c.get('/bom/products/6/versions').json()[0]['version_num']==1
    spring=create_spring(c) if not c.get('/bom/products/7/versions').json() else c.get('/bom/products/7/versions').json()[0]['id_spec_version']
    only_assembly=post(c,'/bom/expand',{'version_id':spring,'category_id':4})
    assert only_assembly['leaf_summary']==[]
    assert len(only_assembly['matched_assemblies'])>=1

def test_optional_line_and_rule_include(env):
    c,_,_=env
    v=add(c,9,[line(8,1), {**line(10,1), 'is_optional':True}],
           config_params=[{'parameter_code':'SIZE','is_required':True}],
           rules=[{'rule_name':'Add card for M','action':'include','target_position_num':2,
                   'conditions':[{'parameter_code':'SIZE','value_text':'M'}]}])['id_spec_version']
    plain=post(c,'/bom/expand',{'version_id':v,'params':{'SIZE':'S'}})
    assert summary_map(plain)=={8:1}
    with_card=post(c,'/bom/expand',{'version_id':v,'params':{'SIZE':'M'}})
    assert summary_map(with_card)=={8:1,10:1}

def test_quantity_denominator_rejects_fractional_integer_at_expansion(env):
    c,_,_=env
    v=add(c,6,[line(1,1)],for_quantity=2)['id_spec_version']
    assert c.post('/bom/expand',json={'version_id':v,'quantity':1}).status_code==400
    assert summary_map(post(c,'/bom/expand',{'version_id':v,'quantity':2}))=={1:1}
