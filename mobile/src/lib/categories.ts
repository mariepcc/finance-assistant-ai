import type { Category } from './types';

export function categoryLabel(
  category: Category | undefined,
  byId: Map<string, Category>,
): string {
  if (!category) return 'Kategoria';
  const parent = category.parent_id ? byId.get(category.parent_id) : undefined;
  return parent ? `${parent.name} · ${category.name}` : category.name;
}

export function joinLabel(category: string, subcategory: string | null): string {
  return subcategory ? `${category} · ${subcategory}` : category;
}
