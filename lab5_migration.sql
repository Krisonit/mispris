-- LAB 5 migration. Run only after backing up flower_shop_new.
-- This adds new tables; existing catalog data is not truncated.
BEGIN;
ALTER TABLE products ADD COLUMN IF NOT EXISTS is_composite BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS spec_versions (
	id_spec_version SERIAL NOT NULL, 
	product_id INTEGER NOT NULL, 
	version_num INTEGER NOT NULL, 
	base_version_id INTEGER, 
	for_quantity NUMERIC(18, 6) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	comment TEXT NOT NULL, 
	PRIMARY KEY (id_spec_version), 
	CONSTRAINT uq_spec_version_product_num UNIQUE (product_id, version_num), 
	FOREIGN KEY(product_id) REFERENCES products (id_product) ON DELETE RESTRICT, 
	FOREIGN KEY(base_version_id) REFERENCES spec_versions (id_spec_version) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS spec_changes (
	id_change SERIAL NOT NULL, 
	spec_version_id INTEGER NOT NULL, 
	subject_key VARCHAR(80) NOT NULL, 
	attribute_name VARCHAR(80) NOT NULL, 
	action VARCHAR(25) NOT NULL, 
	old_value TEXT, 
	new_value TEXT, 
	changed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	comment TEXT NOT NULL, 
	PRIMARY KEY (id_change), 
	FOREIGN KEY(spec_version_id) REFERENCES spec_versions (id_spec_version) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS spec_config_params (
	id_config_param SERIAL NOT NULL, 
	spec_version_id INTEGER NOT NULL, 
	parameter_id INTEGER NOT NULL, 
	is_required BOOLEAN NOT NULL, 
	min_override NUMERIC(18, 6), 
	max_override NUMERIC(18, 6), 
	default_value TEXT, 
	PRIMARY KEY (id_config_param), 
	CONSTRAINT uq_spec_config_param UNIQUE (spec_version_id, parameter_id), 
	FOREIGN KEY(spec_version_id) REFERENCES spec_versions (id_spec_version) ON DELETE RESTRICT, 
	FOREIGN KEY(parameter_id) REFERENCES parameters (id_parameter) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS spec_items (
	id_spec_item SERIAL NOT NULL, 
	spec_version_id INTEGER NOT NULL, 
	position_num INTEGER NOT NULL, 
	action VARCHAR(20) NOT NULL, 
	target_item_id INTEGER, 
	component_version_id INTEGER, 
	quantity NUMERIC(18, 6), 
	is_optional BOOLEAN, 
	PRIMARY KEY (id_spec_item), 
	CONSTRAINT uq_spec_item_position UNIQUE (spec_version_id, position_num), 
	FOREIGN KEY(spec_version_id) REFERENCES spec_versions (id_spec_version) ON DELETE RESTRICT, 
	FOREIGN KEY(target_item_id) REFERENCES spec_items (id_spec_item) ON DELETE RESTRICT, 
	FOREIGN KEY(component_version_id) REFERENCES spec_versions (id_spec_version) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS variant_nodes (
	id_node SERIAL NOT NULL, 
	parent_node_id INTEGER, 
	node_num INTEGER NOT NULL, 
	spec_version_id INTEGER NOT NULL, 
	quantity NUMERIC(18, 6) NOT NULL, 
	PRIMARY KEY (id_node), 
	FOREIGN KEY(parent_node_id) REFERENCES variant_nodes (id_node) ON DELETE RESTRICT, 
	FOREIGN KEY(spec_version_id) REFERENCES spec_versions (id_spec_version) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS spec_param_links (
	id_link SERIAL NOT NULL, 
	child_item_id INTEGER NOT NULL, 
	source_config_param_id INTEGER NOT NULL, 
	target_config_param_id INTEGER NOT NULL, 
	PRIMARY KEY (id_link), 
	FOREIGN KEY(child_item_id) REFERENCES spec_items (id_spec_item) ON DELETE RESTRICT, 
	FOREIGN KEY(source_config_param_id) REFERENCES spec_config_params (id_config_param) ON DELETE RESTRICT, 
	FOREIGN KEY(target_config_param_id) REFERENCES spec_config_params (id_config_param) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS spec_rules (
	id_rule SERIAL NOT NULL, 
	spec_version_id INTEGER NOT NULL, 
	rule_name VARCHAR(120) NOT NULL, 
	action VARCHAR(20) NOT NULL, 
	target_item_id INTEGER, 
	result_version_id INTEGER, 
	result_quantity NUMERIC(18, 6), 
	message TEXT, 
	PRIMARY KEY (id_rule), 
	FOREIGN KEY(spec_version_id) REFERENCES spec_versions (id_spec_version) ON DELETE RESTRICT, 
	FOREIGN KEY(target_item_id) REFERENCES spec_items (id_spec_item) ON DELETE RESTRICT, 
	FOREIGN KEY(result_version_id) REFERENCES spec_versions (id_spec_version) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS spec_variants (
	id_variant SERIAL NOT NULL, 
	root_node_id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id_variant), 
	UNIQUE (root_node_id), 
	FOREIGN KEY(root_node_id) REFERENCES variant_nodes (id_node) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS variant_values (
	node_id INTEGER NOT NULL, 
	config_param_id INTEGER NOT NULL, 
	value_text TEXT NOT NULL, 
	PRIMARY KEY (node_id, config_param_id), 
	FOREIGN KEY(node_id) REFERENCES variant_nodes (id_node) ON DELETE RESTRICT, 
	FOREIGN KEY(config_param_id) REFERENCES spec_config_params (id_config_param) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS spec_rule_conditions (
	id_condition SERIAL NOT NULL, 
	rule_id INTEGER NOT NULL, 
	group_num INTEGER NOT NULL, 
	condition_num INTEGER NOT NULL, 
	config_param_id INTEGER NOT NULL, 
	operator VARCHAR(12) NOT NULL, 
	value_text TEXT, 
	right_config_param_id INTEGER, 
	PRIMARY KEY (id_condition), 
	CONSTRAINT uq_rule_condition_pos UNIQUE (rule_id, group_num, condition_num), 
	FOREIGN KEY(rule_id) REFERENCES spec_rules (id_rule) ON DELETE RESTRICT, 
	FOREIGN KEY(config_param_id) REFERENCES spec_config_params (id_config_param) ON DELETE RESTRICT, 
	FOREIGN KEY(right_config_param_id) REFERENCES spec_config_params (id_config_param) ON DELETE RESTRICT
);

COMMIT;
