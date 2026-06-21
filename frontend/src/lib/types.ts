export interface Me {
  id: string;
  email: string;
  full_name: string;
  is_superadmin: boolean;
  permissions: string[];
  roles: { code: string; name: string }[];
}

export interface ModuleDef {
  id: string;
  code: string;
  name: string;
  slug: string;
  description?: string;
  icon: string;
  priority?: string;
  release_bucket?: string;
}

export interface MenuItem {
  id: string;
  label: string;
  icon: string;
  path: string;
  module_slug?: string;
  permission_code?: string;
  sort_order: number;
}

export interface FieldDef {
  name: string;
  label: string;
  data_type: string;
  is_required: boolean;
  is_unique: boolean;
  is_list_visible: boolean;
  options_master?: string | null;
  reference_entity?: string | null;
  default_value?: string | null;
  sort_order: number;
  help_text?: string | null;
}

export interface EntityDef {
  id: string;
  name: string;
  slug: string;
  kind: string;
  purpose?: string;
  is_typed: boolean;
  typed_table?: string | null;
  icon: string;
  fields: FieldDef[];
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}
