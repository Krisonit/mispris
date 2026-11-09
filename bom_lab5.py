"""Lab 5: versioned Bill of Materials for the existing flower_shop application.

All product/category/parameter/unit records are reused from main_new.py.  The
HTTP API is under /bom; nothing in catalog1.html needs to be changed.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Session


class ItemIn(BaseModel):
    action: str = 'add'                  # add / exclude / replace / quantity
    position_num: Optional[int] = None
    target_item_id: Optional[int] = None
    component_product_id: Optional[int] = None
    component_version_id: Optional[int] = None
    quantity: Optional[Decimal] = None
    is_optional: Optional[bool] = None

class ConfigIn(BaseModel):
    parameter_code: str
    is_required: bool = False
    min_override: Optional[Decimal] = None
    max_override: Optional[Decimal] = None
    default_value: Optional[str] = None

class ConditionIn(BaseModel):
    group_num: int = 1
    condition_num: int = 1
    parameter_code: str
    operator: str = 'eq'
    value_text: Optional[str] = None
    right_parameter_code: Optional[str] = None

class RuleIn(BaseModel):
    rule_name: str
    action: str
    target_item_id: Optional[int] = None
    target_position_num: Optional[int] = None
    result_component_product_id: Optional[int] = None
    result_version_id: Optional[int] = None
    result_quantity: Optional[Decimal] = None
    message: Optional[str] = None
    conditions: List[ConditionIn] = Field(default_factory=list)

class ParamLinkIn(BaseModel):
    child_item_id: Optional[int] = None
    child_position_num: Optional[int] = None
    source_parameter_code: str
    target_parameter_code: str

class VersionIn(BaseModel):
    base_version_id: Optional[int] = None
    for_quantity: Decimal = Decimal('1')
    comment: str = ''
    items: List[ItemIn] = Field(default_factory=list)
    config_params: List[ConfigIn] = Field(default_factory=list)
    rules: List[RuleIn] = Field(default_factory=list)
    param_links: List[ParamLinkIn] = Field(default_factory=list)

class ModificationIn(BaseModel):
    name: str
    code: str
    base_version_id: int
    comment: str = ''
    items: List[ItemIn] = Field(default_factory=list)
    config_params: List[ConfigIn] = Field(default_factory=list)
    rules: List[RuleIn] = Field(default_factory=list)
    param_links: List[ParamLinkIn] = Field(default_factory=list)

class ExpandIn(BaseModel):
    product_id: Optional[int] = None
    version_id: Optional[int] = None
    quantity: Decimal = Decimal('1')
    params: Dict[str, str] = Field(default_factory=dict)
    # Key is a slash-separated path of BOM item IDs, e.g. "17/24".
    node_values: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    category_id: Optional[int] = None

class VariantIn(ExpandIn):
    name: str


def install_bom(app, Base, get_db, Product, Category, Unit, Parameter, ParamType, EnumValue):
    """Register new SQLAlchemy models and FastAPI endpoints in an existing app."""

    class SpecVersion(Base):
        __tablename__ = 'spec_versions'
        id_spec_version = Column(Integer, primary_key=True)
        product_id = Column(Integer, ForeignKey('products.id_product', ondelete='RESTRICT'), nullable=False)
        version_num = Column(Integer, nullable=False)
        base_version_id = Column(Integer, ForeignKey('spec_versions.id_spec_version', ondelete='RESTRICT'))
        for_quantity = Column(Numeric(18, 6), nullable=False, default=1)
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        comment = Column(Text, nullable=False, default='')
        __table_args__ = (UniqueConstraint('product_id', 'version_num', name='uq_spec_version_product_num'),)

    class SpecItem(Base):
        __tablename__ = 'spec_items'
        id_spec_item = Column(Integer, primary_key=True)
        spec_version_id = Column(Integer, ForeignKey('spec_versions.id_spec_version', ondelete='RESTRICT'), nullable=False)
        position_num = Column(Integer, nullable=False)
        action = Column(String(20), nullable=False, default='add')
        target_item_id = Column(Integer, ForeignKey('spec_items.id_spec_item', ondelete='RESTRICT'))
        component_version_id = Column(Integer, ForeignKey('spec_versions.id_spec_version', ondelete='RESTRICT'))
        quantity = Column(Numeric(18, 6))
        is_optional = Column(Boolean)
        __table_args__ = (UniqueConstraint('spec_version_id', 'position_num', name='uq_spec_item_position'),)

    class SpecChange(Base):
        __tablename__ = 'spec_changes'
        id_change = Column(Integer, primary_key=True)
        spec_version_id = Column(Integer, ForeignKey('spec_versions.id_spec_version', ondelete='RESTRICT'), nullable=False)
        subject_key = Column(String(80), nullable=False)
        attribute_name = Column(String(80), nullable=False)
        action = Column(String(25), nullable=False)
        old_value = Column(Text)
        new_value = Column(Text)
        changed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        comment = Column(Text, nullable=False, default='')

    class SpecConfigParam(Base):
        __tablename__ = 'spec_config_params'
        id_config_param = Column(Integer, primary_key=True)
        spec_version_id = Column(Integer, ForeignKey('spec_versions.id_spec_version', ondelete='RESTRICT'), nullable=False)
        parameter_id = Column(Integer, ForeignKey('parameters.id_parameter', ondelete='RESTRICT'), nullable=False)
        is_required = Column(Boolean, nullable=False, default=False)
        min_override = Column(Numeric(18, 6))
        max_override = Column(Numeric(18, 6))
        default_value = Column(Text)
        __table_args__ = (UniqueConstraint('spec_version_id', 'parameter_id', name='uq_spec_config_param'),)

    class SpecRule(Base):
        __tablename__ = 'spec_rules'
        id_rule = Column(Integer, primary_key=True)
        spec_version_id = Column(Integer, ForeignKey('spec_versions.id_spec_version', ondelete='RESTRICT'), nullable=False)
        rule_name = Column(String(120), nullable=False)
        action = Column(String(20), nullable=False)
        target_item_id = Column(Integer, ForeignKey('spec_items.id_spec_item', ondelete='RESTRICT'))
        result_version_id = Column(Integer, ForeignKey('spec_versions.id_spec_version', ondelete='RESTRICT'))
        result_quantity = Column(Numeric(18, 6))
        message = Column(Text)

    class SpecRuleCondition(Base):
        __tablename__ = 'spec_rule_conditions'
        id_condition = Column(Integer, primary_key=True)
        rule_id = Column(Integer, ForeignKey('spec_rules.id_rule', ondelete='RESTRICT'), nullable=False)
        group_num = Column(Integer, nullable=False)
        condition_num = Column(Integer, nullable=False)
        config_param_id = Column(Integer, ForeignKey('spec_config_params.id_config_param', ondelete='RESTRICT'), nullable=False)
        operator = Column(String(12), nullable=False)
        value_text = Column(Text)
        right_config_param_id = Column(Integer, ForeignKey('spec_config_params.id_config_param', ondelete='RESTRICT'))
        __table_args__ = (UniqueConstraint('rule_id', 'group_num', 'condition_num', name='uq_rule_condition_pos'),)

    class SpecParamLink(Base):
        __tablename__ = 'spec_param_links'
        id_link = Column(Integer, primary_key=True)
        child_item_id = Column(Integer, ForeignKey('spec_items.id_spec_item', ondelete='RESTRICT'), nullable=False)
        source_config_param_id = Column(Integer, ForeignKey('spec_config_params.id_config_param', ondelete='RESTRICT'), nullable=False)
        target_config_param_id = Column(Integer, ForeignKey('spec_config_params.id_config_param', ondelete='RESTRICT'), nullable=False)

    class VariantNode(Base):
        __tablename__ = 'variant_nodes'
        id_node = Column(Integer, primary_key=True)
        parent_node_id = Column(Integer, ForeignKey('variant_nodes.id_node', ondelete='RESTRICT'))
        node_num = Column(Integer, nullable=False)
        spec_version_id = Column(Integer, ForeignKey('spec_versions.id_spec_version', ondelete='RESTRICT'), nullable=False)
        quantity = Column(Numeric(18, 6), nullable=False)

    class SpecVariant(Base):
        __tablename__ = 'spec_variants'
        id_variant = Column(Integer, primary_key=True)
        root_node_id = Column(Integer, ForeignKey('variant_nodes.id_node', ondelete='RESTRICT'), nullable=False, unique=True)
        name = Column(String(200), nullable=False)
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    class VariantValue(Base):
        __tablename__ = 'variant_values'
        node_id = Column(Integer, ForeignKey('variant_nodes.id_node', ondelete='RESTRICT'), primary_key=True)
        config_param_id = Column(Integer, ForeignKey('spec_config_params.id_config_param', ondelete='RESTRICT'), primary_key=True)
        value_text = Column(Text, nullable=False)

    # Expose models for smoke tests; the user's original classes are unchanged.
    app.state.bom_models = {
        'SpecVersion': SpecVersion, 'SpecItem': SpecItem, 'SpecChange': SpecChange,
        'SpecConfigParam': SpecConfigParam, 'SpecRule': SpecRule,
        'SpecRuleCondition': SpecRuleCondition, 'SpecParamLink': SpecParamLink,
        'SpecVariant': SpecVariant, 'VariantNode': VariantNode, 'VariantValue': VariantValue,
    }

    def fail(message, code=400):
        raise HTTPException(status_code=code, detail=message)

    def dec(value, label='Количество'):
        try:
            result = Decimal(str(value))
            if not result.is_finite():
                raise ValueError
            return result
        except (ValueError, TypeError, InvalidOperation):
            fail(f'{label}: требуется конечное число')

    def positive(value, label='Количество'):
        number = dec(value, label)
        if number <= 0:
            fail(f'{label} должно быть больше нуля')
        if number != number.quantize(Decimal('0.000001')):
            fail(f'{label}: допускается не более шести знаков после запятой')
        return number

    def fmt(value):
        v = dec(value)
        return int(v) if v == v.to_integral_value() else float(v)

    def get_product(db, product_id):
        p = db.get(Product, product_id)
        if not p:
            fail(f'Товар {product_id} не найден', 404)
        return p

    def get_version(db, version_id):
        v = db.get(SpecVersion, version_id)
        if not v:
            fail(f'Версия спецификации {version_id} не найдена', 404)
        return v

    def unit_for(db, product):
        u = db.get(Unit, product.unit_id) if product.unit_id else None
        if not u:
            fail(f'У товара {product.name} отсутствует единица измерения')
        return u

    def integer_quantity(db, product, quantity):
        q = positive(quantity)
        u = unit_for(db, product)
        if u.is_integer_only and q != q.to_integral_value():
            fail(f'Для товара «{product.name}» единица «{u.short_name}» требует целого количества: {q}')
        return q

    def product_of_version(db, v):
        return get_product(db, v.product_id)

    def latest(db, product_id):
        return db.query(SpecVersion).filter_by(product_id=product_id).order_by(SpecVersion.version_num.desc()).first()

    def ensure_leaf(db, product_id):
        p = get_product(db, product_id)
        v = latest(db, product_id)
        if v:
            return v
        if p.is_composite:
            fail(f'Составной товар «{p.name}» не имеет спецификации')
        v = SpecVersion(product_id=product_id, version_num=1, for_quantity=1,
                        comment='Автоматическая пустая версия простого товара')
        db.add(v)
        db.flush()
        return v

    def item_rows(db, version_id):
        return db.query(SpecItem).filter_by(spec_version_id=version_id).order_by(SpecItem.position_num).all()

    def line_dict(row, v):
        return {'id': row.id_spec_item, 'position_num': row.position_num,
                'component_version_id': row.component_version_id,
                'quantity': dec(row.quantity), 'for_quantity': dec(v.for_quantity),
                'is_optional': bool(row.is_optional), 'source_version_id': v.id_spec_version}

    def effective(db, version_id, seen=None):
        """Resolve immutable base + ordered modification deltas; stable origin item IDs."""
        seen = set() if seen is None else seen
        if version_id in seen:
            fail('Цикл цепочки модификаций')
        seen = seen | {version_id}
        v = get_version(db, version_id)
        entries = effective(db, v.base_version_id, seen) if v.base_version_id else {}
        for row in item_rows(db, version_id):
            action = row.action
            if action == 'add':
                entries[row.id_spec_item] = line_dict(row, v)
            else:
                target = row.target_item_id
                if target not in entries:
                    fail(f'Позиция {target} не найдена в основе модификации {version_id}')
                if action == 'exclude':
                    del entries[target]
                elif action == 'replace':
                    entries[target] = {**entries[target], 'component_version_id': row.component_version_id,
                                       'quantity': dec(row.quantity), 'is_optional': bool(row.is_optional)
                                       if row.is_optional is not None else entries[target]['is_optional']}
                elif action == 'quantity':
                    entries[target] = {**entries[target], 'quantity': dec(row.quantity)}
                else:
                    fail(f'Неизвестное действие в спецификации: {action}')
        return entries

    def lineage(db, version_id):
        result = []
        seen = set()
        v = get_version(db, version_id)
        while v:
            if v.id_spec_version in seen:
                fail('Цикл основ модификаций')
            seen.add(v.id_spec_version)
            result.append(v)
            v = get_version(db, v.base_version_id) if v.base_version_id else None
        return list(reversed(result))

    def configs(db, version_id):
        merged = {}
        for v in lineage(db, version_id):
            for cp in db.query(SpecConfigParam).filter_by(spec_version_id=v.id_spec_version).all():
                p = db.get(Parameter, cp.parameter_id)
                if p:
                    merged[p.code] = (cp, p)
        return merged

    def rules(db, version_id):
        result = []
        for v in lineage(db, version_id):
            result.extend(db.query(SpecRule).filter_by(spec_version_id=v.id_spec_version).all())
        return result

    def meta_config(db, config_id):
        c = db.get(SpecConfigParam, config_id)
        if not c:
            fail(f'Параметр конфигурации {config_id} не найден')
        p = db.get(Parameter, c.parameter_id)
        if not p:
            fail('Ссылка на отсутствующий параметр')
        return c, p

    def typed_value(db, c, p, value, check_bounds=True):
        typ = db.get(ParamType, p.id_param_type)
        if not typ:
            fail(f'Неизвестный тип параметра {p.code}')
        if value is None:
            return None
        if typ.sys_code in ('integer', 'float', 'decimal', 'numeric', 'real'):
            n = dec(value, p.name)
            if typ.sys_code == 'integer' and n != n.to_integral_value():
                fail(f'Параметр {p.code}: требуется целое число')
            lower = c.min_override if c.min_override is not None else p.min_value
            upper = c.max_override if c.max_override is not None else p.max_value
            if check_bounds and lower is not None and n < dec(lower):
                fail(f'Параметр {p.code} меньше минимума {lower}')
            if check_bounds and upper is not None and n > dec(upper):
                fail(f'Параметр {p.code} больше максимума {upper}')
            return n
        if typ.sys_code == 'enum':
            entries = db.query(EnumValue).filter_by(parameter_id=p.id_parameter).all()
            match = next((e for e in entries if str(value) in (
                str(e.id_enum_value), e.value_code, e.value_name)), None)
            if not match:
                fail(f'Параметр {p.code}: недопустимое значение «{value}»')
            return match.value_code or match.value_name
        return str(value)

    def selection(db, version_id, supplied, inherited=None):
        all_configs = configs(db, version_id)
        supplied = supplied or {}
        unknown = set(supplied) - set(all_configs)
        if unknown:
            fail('Неизвестные параметры спецификации: ' + ', '.join(sorted(unknown)))
        chosen = {}
        for code, (cp, param) in all_configs.items():
            raw = supplied.get(code, (inherited or {}).get(code, cp.default_value))
            if raw is None:
                if cp.is_required:
                    fail(f'Не указан обязательный параметр {code}')
                continue
            chosen[code] = typed_value(db, cp, param, raw)
        return chosen

    def conditions_met(db, rule, chosen):
        conditions = db.query(SpecRuleCondition).filter_by(rule_id=rule.id_rule).all()
        if not conditions:
            return True
        groups = defaultdict(list)
        for c in conditions:
            groups[c.group_num].append(c)
        for group in groups.values():
            matches = []
            for condition in group:
                cp, param = meta_config(db, condition.config_param_id)
                left = chosen.get(param.code)
                right = None
                if condition.right_config_param_id is not None:
                    _, rp = meta_config(db, condition.right_config_param_id)
                    right = chosen.get(rp.code)
                elif condition.value_text is not None:
                    if condition.operator == 'in':
                        try:
                            vals = json.loads(condition.value_text)
                            if not isinstance(vals, list):
                                vals = [vals]
                        except (ValueError, TypeError):
                            vals = [s.strip() for s in condition.value_text.split(',')]
                        right = [typed_value(db, cp, param, x, check_bounds=False) for x in vals]
                    else:
                        right = typed_value(db, cp, param, condition.value_text, check_bounds=False)
                op = condition.operator
                if left is None or right is None:
                    matches.append(False)
                elif op == 'eq': matches.append(left == right)
                elif op == 'ne': matches.append(left != right)
                elif op == 'gt':
                    if type(left) is not type(right): fail('Несовместимые типы параметров в сравнении')
                    matches.append(left > right)
                elif op == 'gte':
                    if type(left) is not type(right): fail('Несовместимые типы параметров в сравнении')
                    matches.append(left >= right)
                elif op == 'lt':
                    if type(left) is not type(right): fail('Несовместимые типы параметров в сравнении')
                    matches.append(left < right)
                elif op == 'lte':
                    if type(left) is not type(right): fail('Несовместимые типы параметров в сравнении')
                    matches.append(left <= right)
                elif op == 'in': matches.append(left in right)
                else: fail(f'Неизвестный оператор условия: {op}')
            if all(matches):
                return True
        return False

    def apply_rules(db, version_id, entries, chosen):
        entries = {k: dict(v) for k, v in entries.items()}
        active_rules = [r for r in rules(db, version_id) if conditions_met(db, r, chosen)]
        affected = set()
        for r in active_rules:
            if r.action == 'forbid':
                fail(r.message or f'Недопустимая конфигурация: {r.rule_name}')
            target = r.target_item_id
            if target in affected:
                fail(f'Конфликт правил для позиции {target}: {r.rule_name}')
            affected.add(target)
            if target not in entries:
                fail(f'Правило «{r.rule_name}» обращается к исключенной позиции {target}')
            item = entries[target]
            if r.action == 'include':
                item['is_optional'] = False
            elif r.action == 'exclude':
                item['is_optional'] = True
            elif r.action == 'replace':
                if r.result_version_id is None:
                    fail(f'Правило {r.rule_name}: версия для замены не указана')
                item['component_version_id'] = r.result_version_id
                if r.result_quantity is not None:
                    item['quantity'] = positive(r.result_quantity)
            elif r.action == 'quantity':
                item['quantity'] = positive(r.result_quantity)
            else:
                fail(f'Неизвестное действие правила: {r.action}')
        return {k: v for k, v in entries.items() if not v['is_optional']}

    def category_ids(db, category_id):
        if category_id is None:
            return None
        if not db.get(Category, category_id):
            fail('Категория для фильтрации не найдена', 404)
        ids, queue = set(), [category_id]
        while queue:
            cid = queue.pop()
            if cid in ids:
                continue
            ids.add(cid)
            queue += [c.id_category for c in db.query(Category).filter_by(parent_id=cid).all()]
        return ids

    def links_for(db, line_id):
        return db.query(SpecParamLink).filter_by(child_item_id=line_id).all()

    def linked_params(db, line_id, parent_chosen):
        passed = {}
        for lnk in links_for(db, line_id):
            _, source = meta_config(db, lnk.source_config_param_id)
            _, target = meta_config(db, lnk.target_config_param_id)
            if source.code in parent_chosen:
                if target.code in passed and passed[target.code] != parent_chosen[source.code]:
                    fail(f'Конфликт передачи параметров {target.code}')
                passed[target.code] = str(parent_chosen[source.code])
        return passed

    def expand_impl(db, req: ExpandIn):
        qty = positive(req.quantity)
        if (req.product_id is None) == (req.version_id is None):
            fail('Укажите либо product_id, либо version_id')
        if req.version_id is not None:
            root_v = get_version(db, req.version_id)
        else:
            p = get_product(db, req.product_id)
            root_v = latest(db, p.id_product)
            if root_v is None:
                if p.is_composite:
                    fail(f'У составного товара {p.name} пока нет спецификации')
                root_v = ensure_leaf(db, p.id_product)
        matched = category_ids(db, req.category_id)
        summary = {}
        assemblies = []

        def walk(version_id, required_qty, path, trail, inherited=None):
            v = get_version(db, version_id)
            product = product_of_version(db, v)
            integer_quantity(db, product, required_qty)
            if product.id_product in trail:
                fail('Цикл состава: ' + ' → '.join(str(x) for x in trail + [product.id_product]))
            current_path = '/'.join(map(str, path))
            supplied = req.params if not path else req.node_values.get(current_path, {})
            chosen = selection(db, version_id, supplied, inherited)
            lines = apply_rules(db, version_id, effective(db, version_id), chosen)
            if not product.is_composite and lines:
                fail(f'Простой товар «{product.name}» не должен содержать позиции состава')
            if product.is_composite and not lines:
                fail(f'Составной товар «{product.name}» не имеет итоговых компонентов')
            node = {'product_id': product.id_product, 'name': product.name,
                    'version_id': version_id, 'quantity': fmt(required_qty),
                    'unit': unit_for(db, product).short_name, 'params': {
                        k: str(val) for k, val in chosen.items()}, 'param_ids': {
                        configs(db, version_id)[k][0].id_config_param: str(val)
                        for k, val in chosen.items()},
                    'path': current_path, 'children': []}
            if not lines:
                if matched is None or product.category_id in matched:
                    key = product.id_product
                    if key not in summary:
                        summary[key] = {'product_id': key, 'name': product.name,
                                        'quantity': Decimal(0), 'unit': node['unit']}
                    summary[key]['quantity'] += required_qty
            else:
                if matched is not None and product.category_id in matched:
                    assemblies.append({'product_id': product.id_product, 'name': product.name,
                                       'quantity': fmt(required_qty), 'unit': node['unit'], 'path': current_path})
                for line in lines.values():
                    child = get_version(db, line['component_version_id'])
                    child_p = product_of_version(db, child)
                    child_qty = required_qty * positive(line['quantity']) / positive(line['for_quantity'])
                    integer_quantity(db, child_p, child_qty)
                    passed = linked_params(db, line['id'], chosen)
                    child_node = walk(child.id_spec_version, child_qty, path + [line['id']],
                                      trail + [product.id_product], passed)
                    child_node['item_id'] = line['id']
                    node['children'].append(child_node)
            return node

        tree = walk(root_v.id_spec_version, qty, [], [])
        output_summary = []
        for v in summary.values():
            output_summary.append({**v, 'quantity': fmt(v['quantity'])})
        output_summary.sort(key=lambda x: x['product_id'])
        return {'tree': tree, 'leaf_summary': output_summary, 'matched_assemblies': assemblies,
                'quantity': fmt(qty), 'category_id': req.category_id}

    def resolve_component(db, item):
        if item.component_version_id is not None:
            v = get_version(db, item.component_version_id)
            if item.component_product_id is not None and v.product_id != item.component_product_id:
                fail('Несоответствие товара и версии компонента')
            return v
        if item.component_product_id is None:
            fail('Для добавления/замены нужен component_product_id или component_version_id')
        return ensure_leaf(db, item.component_product_id)

    def save_version(db, product_id, req: VersionIn):
        p = get_product(db, product_id)
        norm = positive(req.for_quantity, 'Норма для количества изделий')
        prev = latest(db, product_id)
        if req.base_version_id is not None:
            parent = get_version(db, req.base_version_id)
            if parent.product_id == product_id:
                fail('Версия не может ссылаться на собственный товар как модификацию')
            # Do not silently change the denominator of inherited items.
            if dec(parent.for_quantity) != norm:
                fail('Норма для количества должна совпадать с основой модификации')
        elif prev and prev.base_version_id is not None:
            fail('Новая версия модификации должна сохранять base_version_id')
        if prev and prev.base_version_id != req.base_version_id:
            fail('Нельзя изменить основу у существующего товара')
        if not req.items and p.is_composite and req.base_version_id is None:
            fail('Составному изделию нужны позиции спецификации')
        if req.items and not p.is_composite:
            p.is_composite = True

        v = SpecVersion(product_id=product_id, version_num=(prev.version_num + 1 if prev else 1),
                        base_version_id=req.base_version_id, for_quantity=norm, comment=req.comment)
        db.add(v)
        db.flush()
        known_targets = effective(db, req.base_version_id) if req.base_version_id else {}
        used_targets = set()
        by_position = {}
        for index, item in enumerate(req.items, 1):
            action = item.action
            if action not in ('add', 'exclude', 'replace', 'quantity'):
                fail('Недопустимое действие в спецификации: ' + action)
            if action != 'add' and not req.base_version_id:
                fail('Исключение/замена/изменение нормы допустимо только для модификации')
            if action != 'add':
                if item.target_item_id not in known_targets:
                    fail(f'Позиция основы {item.target_item_id} не найдена')
                if item.target_item_id in used_targets:
                    fail('Повторное изменение одной строки в одной версии')
                used_targets.add(item.target_item_id)
            target_v = None
            if action in ('add', 'replace'):
                target_v = resolve_component(db, item)
                if target_v.product_id == product_id:
                    fail('Товар не может входить в свой состав напрямую')
            q = positive(item.quantity) if action in ('add', 'replace', 'quantity') else None
            if action == 'quantity':
                # An inherited component may use an integer-only unit.
                target_v = get_version(db, known_targets[item.target_item_id]['component_version_id'])
            if target_v and q:
                integer_quantity(db, product_of_version(db, target_v), q)
            if action == 'quantity':
                target_v = None  # No new component version is written for quantity delta.
            row = SpecItem(spec_version_id=v.id_spec_version,
                           position_num=item.position_num or index, action=action,
                           target_item_id=item.target_item_id,
                           component_version_id=target_v.id_spec_version if target_v else None,
                           quantity=q, is_optional=item.is_optional)
            db.add(row)
            db.flush()
            by_position[row.position_num] = row

        # Save configurable parameters for this version; inherited ones remain immutable.
        available = configs(db, req.base_version_id) if req.base_version_id else {}
        for item in req.config_params:
            pmeta = db.query(Parameter).filter_by(code=item.parameter_code).first()
            if not pmeta:
                fail(f'Параметр {item.parameter_code} отсутствует в справочнике')
            c = SpecConfigParam(spec_version_id=v.id_spec_version, parameter_id=pmeta.id_parameter,
                                is_required=item.is_required, min_override=item.min_override,
                                max_override=item.max_override, default_value=item.default_value)
            db.add(c)
            db.flush()
            available[pmeta.code] = (c, pmeta)
            if c.min_override is not None and c.max_override is not None and c.min_override > c.max_override:
                fail('Минимум больше максимума для параметра ' + pmeta.code)
            if item.default_value is not None:
                typed_value(db, c, pmeta, item.default_value)

        # Rules reference a line through its original ID or its local position.
        for rule in req.rules:
            if rule.action not in ('include', 'exclude', 'replace', 'quantity', 'forbid'):
                fail('Недопустимое действие правила: ' + rule.action)
            target = rule.target_item_id
            if rule.target_position_num is not None:
                row = by_position.get(rule.target_position_num)
                if not row:
                    fail(f'Позиция {rule.target_position_num} не найдена')
                target = row.id_spec_item if row.action == 'add' else row.target_item_id
            if rule.action != 'forbid' and target is None:
                fail('У правила действия не указана позиция')
            if rule.action != 'forbid' and target not in effective(db, v.id_spec_version):
                fail(f'Правило «{rule.rule_name}» обращается к отсутствующей позиции {target}')
            result_v = None
            if rule.result_version_id is not None:
                result_v = get_version(db, rule.result_version_id)
            elif rule.result_component_product_id is not None:
                result_v = ensure_leaf(db, rule.result_component_product_id)
            if rule.action == 'replace' and result_v is None:
                fail('Правилу замены требуется новый компонент')
            if rule.action == 'quantity':
                positive(rule.result_quantity)
            rr = SpecRule(spec_version_id=v.id_spec_version, rule_name=rule.rule_name,
                          action=rule.action, target_item_id=target,
                          result_version_id=result_v.id_spec_version if result_v else None,
                          result_quantity=rule.result_quantity, message=rule.message)
            db.add(rr)
            db.flush()
            for cnd in rule.conditions:
                if cnd.operator not in ('eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in'):
                    fail('Неизвестный оператор: ' + cnd.operator)
                if cnd.parameter_code not in available:
                    fail('Параметр правила не описан: ' + cnd.parameter_code)
                if cnd.right_parameter_code and cnd.right_parameter_code not in available:
                    fail('Правый параметр правила не описан: ' + cnd.right_parameter_code)
                c_id = available[cnd.parameter_code][0].id_config_param
                right_id = available[cnd.right_parameter_code][0].id_config_param if cnd.right_parameter_code else None
                if right_id is None and cnd.value_text is None:
                    fail('Условие без правого операнда')
                if right_id is None and cnd.value_text is not None:
                    cmeta, pmeta = available[cnd.parameter_code]
                    if cnd.operator == 'in':
                        try:
                            check_values = json.loads(cnd.value_text)
                            if not isinstance(check_values, list): check_values = [check_values]
                        except (ValueError, TypeError):
                            check_values = [v.strip() for v in cnd.value_text.split(',')]
                        for value in check_values:
                            typed_value(db, cmeta, pmeta, value, check_bounds=False)
                    else:
                        typed_value(db, cmeta, pmeta, cnd.value_text, check_bounds=False)
                db.add(SpecRuleCondition(rule_id=rr.id_rule, group_num=cnd.group_num,
                                         condition_num=cnd.condition_num, config_param_id=c_id,
                                         operator=cnd.operator, value_text=cnd.value_text,
                                         right_config_param_id=right_id))

        for link in req.param_links:
            child_id = link.child_item_id
            if link.child_position_num is not None:
                row = by_position.get(link.child_position_num)
                if not row or row.action != 'add':
                    fail('Ссылка на вложенный элемент должна указывать на добавленную строку')
                child_id = row.id_spec_item
            if child_id is None:
                fail('Не указан вложенный компонент для передачи параметра')
            target_line = next((row for row in effective(db, v.id_spec_version).values() if row['id'] == child_id), None)
            if not target_line:
                fail('Указана отсутствующая строка для передачи параметров')
            if link.source_parameter_code not in available:
                fail('Отсутствует исходный параметр ' + link.source_parameter_code)
            child_configs = configs(db, target_line['component_version_id'])
            if link.target_parameter_code not in child_configs:
                fail('Вложенный товар не имеет параметра ' + link.target_parameter_code)
            db.add(SpecParamLink(child_item_id=child_id,
                                 source_config_param_id=available[link.source_parameter_code][0].id_config_param,
                                 target_config_param_id=child_configs[link.target_parameter_code][0].id_config_param))

        # Immutable version history.  A full new normal version replaces its old
        # list; a modification stores deltas against its pinned base version.
        db.flush()
        present = {r.position_num: r for r in item_rows(db, v.id_spec_version)}
        old = {r.position_num: r for r in item_rows(db, prev.id_spec_version)} if prev else {}
        for position in sorted(set(old) | set(present)):
            a, b = old.get(position), present.get(position)
            a_repr = None if a is None else json.dumps({'action': a.action, 'target': a.target_item_id,
                'component_version': a.component_version_id, 'qty': str(a.quantity)}, ensure_ascii=False)
            b_repr = None if b is None else json.dumps({'action': b.action, 'target': b.target_item_id,
                'component_version': b.component_version_id, 'qty': str(b.quantity)}, ensure_ascii=False)
            if a_repr != b_repr:
                db.add(SpecChange(spec_version_id=v.id_spec_version,
                    subject_key=f'position:{position}', attribute_name='spec_item',
                    action='add' if a is None else ('exclude' if b is None else 'update'),
                    old_value=a_repr, new_value=b_repr, comment=req.comment))
        db.add(SpecChange(spec_version_id=v.id_spec_version, subject_key=f'version:{v.id_spec_version}',
                          attribute_name='version', action='create', old_value=str(prev.version_num) if prev else None,
                          new_value=str(v.version_num), comment=req.comment))
        db.flush()
        # Validate static composition even when optional lines/rules are not active;
        # disallow an item that references an ancestor product through nested specs.
        def static_check(current_version_id, ancestry):
            sv = get_version(db, current_version_id)
            if sv.product_id in ancestry:
                fail('Цикл в составе изделия: ' + ' -> '.join(map(str, ancestry + [sv.product_id])))
            for entry in effective(db, current_version_id).values():
                static_check(entry['component_version_id'], ancestry + [sv.product_id])
            for r in rules(db, current_version_id):
                if r.action == 'replace' and r.result_version_id:
                    static_check(r.result_version_id, ancestry + [sv.product_id])
        static_check(v.id_spec_version, [])
        return v

    def public_version(db, v):
        p = get_product(db, v.product_id)
        return {'id_spec_version': v.id_spec_version, 'product_id': v.product_id,
                'product_name': p.name, 'version_num': v.version_num,
                'base_version_id': v.base_version_id, 'for_quantity': fmt(v.for_quantity),
                'created_at': v.created_at, 'comment': v.comment}

    @app.get('/bom/products/{product_id}/versions')
    def get_versions(product_id: int, db: Session = Depends(get_db)):
        get_product(db, product_id)
        return [public_version(db, v) for v in db.query(SpecVersion).filter_by(product_id=product_id)
                .order_by(SpecVersion.version_num).all()]

    @app.post('/bom/products/{product_id}/versions')
    def create_version(product_id: int, body: VersionIn, db: Session = Depends(get_db)):
        try:
            v = save_version(db, product_id, body)
            db.commit()
            return public_version(db, v)
        except Exception:
            db.rollback()
            raise

    @app.get('/bom/versions/{version_id}')
    def view_version(version_id: int, db: Session = Depends(get_db)):
        v = get_version(db, version_id)
        rows = item_rows(db, v.id_spec_version)
        resolved = effective(db, v.id_spec_version)
        return {'version': public_version(db, v), 'items': [{
            'id': r.id_spec_item, 'position_num': r.position_num, 'action': r.action,
            'target_item_id': r.target_item_id, 'component_version_id': r.component_version_id,
            'quantity': fmt(r.quantity) if r.quantity is not None else None,
            'is_optional': r.is_optional,
        } for r in rows],
        'effective_items': [{**{k: (fmt(val) if isinstance(val, Decimal) else val)
                          for k, val in line.items()}} for line in resolved.values()],
        'config_params': [{'config_param_id': cp.id_config_param, 'parameter_code': p.code,
                           'is_required': cp.is_required, 'default_value': cp.default_value}
                          for cp, p in configs(db, v.id_spec_version).values()]}

    @app.post('/bom/modifications')
    def create_modification(body: ModificationIn, db: Session = Depends(get_db)):
        try:
            base = get_version(db, body.base_version_id)
            original = product_of_version(db, base)
            if db.query(Product).filter_by(code=body.code).first():
                fail(f'Код товара {body.code} уже существует')
            modified = Product(name=body.name, code=body.code, category_id=original.category_id,
                               unit_id=original.unit_id, price=original.price, is_composite=True)
            db.add(modified)
            db.flush()
            v = save_version(db, modified.id_product, VersionIn(
                base_version_id=base.id_spec_version, for_quantity=dec(base.for_quantity),
                comment=body.comment, items=body.items, config_params=body.config_params,
                rules=body.rules, param_links=body.param_links))
            db.commit()
            return {'product_id': modified.id_product, 'version': public_version(db, v)}
        except Exception:
            db.rollback()
            raise

    @app.post('/bom/expand')
    def expand(body: ExpandIn, db: Session = Depends(get_db)):
        try:
            output = expand_impl(db, body)
            # Auto-created empty versions for simple components are persisted.
            db.commit()
            return output
        except Exception:
            db.rollback()
            raise

    @app.post('/bom/variants')
    def save_variant(body: VariantIn, db: Session = Depends(get_db)):
        try:
            output = expand_impl(db, body)
            def store(node, parent_id=None, ordinal=1):
                new = VariantNode(parent_node_id=parent_id, node_num=ordinal,
                                  spec_version_id=node['version_id'], quantity=dec(node['quantity']))
                db.add(new)
                db.flush()
                for cp_id, value in node['param_ids'].items():
                    db.add(VariantValue(node_id=new.id_node, config_param_id=cp_id, value_text=value))
                for index, child in enumerate(node['children'], 1):
                    store(child, new.id_node, index)
                return new.id_node
            root_id = store(output['tree'])
            new_variant = SpecVariant(root_node_id=root_id, name=body.name)
            db.add(new_variant)
            db.commit()
            return {'id_variant': new_variant.id_variant, 'name': new_variant.name,
                    'root_node_id': root_id, 'leaf_summary': output['leaf_summary']}
        except Exception:
            db.rollback()
            raise

    @app.get('/bom/variants/{variant_id}')
    def get_variant(variant_id: int, category_id: Optional[int] = None, db: Session = Depends(get_db)):
        variant = db.get(SpecVariant, variant_id)
        if not variant:
            fail('Вариант не найден', 404)
        matched = category_ids(db, category_id)
        summary, assemblies = {}, []
        def restore(node_id):
            record = db.get(VariantNode, node_id)
            version = get_version(db, record.spec_version_id)
            p = get_product(db, version.product_id)
            child_records = db.query(VariantNode).filter_by(parent_node_id=node_id).order_by(VariantNode.node_num).all()
            node = {'node_id': node_id, 'product_id': p.id_product, 'name': p.name,
                    'version_id': version.id_spec_version, 'quantity': fmt(record.quantity),
                    'unit': unit_for(db, p).short_name,
                    'params': {meta_config(db, val.config_param_id)[1].code: val.value_text
                               for val in db.query(VariantValue).filter_by(node_id=node_id).all()},
                    'children': [restore(c.id_node) for c in child_records]}
            if not child_records:
                if matched is None or p.category_id in matched:
                    if p.id_product not in summary:
                        summary[p.id_product] = {'product_id': p.id_product, 'name': p.name,
                                                'quantity': Decimal(0), 'unit': node['unit']}
                    summary[p.id_product]['quantity'] += dec(record.quantity)
            elif matched is not None and p.category_id in matched:
                assemblies.append({'product_id': p.id_product, 'name': p.name,
                                   'quantity': fmt(record.quantity), 'unit': node['unit']})
            return node
        root = restore(variant.root_node_id)
        return {'id_variant': variant.id_variant, 'name': variant.name,
                'tree': root, 'leaf_summary': [{**v, 'quantity': fmt(v['quantity'])}
                                              for v in sorted(summary.values(), key=lambda v: v['product_id'])],
                'matched_assemblies': assemblies}

    @app.get('/bom/products/{product_id}/history')
    def history(product_id: int, db: Session = Depends(get_db)):
        get_product(db, product_id)
        vers = db.query(SpecVersion).filter_by(product_id=product_id).all()
        result = []
        for v in vers:
            changes = db.query(SpecChange).filter_by(spec_version_id=v.id_spec_version).all()
            result.append({'version': public_version(db, v), 'changes': [{
                'subject': c.subject_key, 'attribute': c.attribute_name,
                'action': c.action, 'old': c.old_value, 'new': c.new_value,
                'comment': c.comment, 'date': c.changed_at} for c in changes]})
        return result

    @app.post('/bom/products/{product_id}/ensure-leaf-version')
    def ensure_leaf_version(product_id: int, db: Session = Depends(get_db)):
        try:
            v = ensure_leaf(db, product_id)
            db.commit()
            return public_version(db, v)
        except Exception:
            db.rollback()
            raise

    return app.state.bom_models
