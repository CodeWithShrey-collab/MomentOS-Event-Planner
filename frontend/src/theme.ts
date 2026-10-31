const categorySlots: Record<string, number> = {
  venue: 1,
  space: 1,
  food: 2,
  catering: 2,
  flowers: 3,
  decor: 3,
  decoration: 3,
  photography: 4,
  photo: 4,
  music: 5,
  sound: 5,
  attire: 6,
  travel: 4,
  reserve: 6,
  safety: 5,
  materials: 3,
  volunteers: 4,
};

const paletteSize = 6;

export function categoryColorToken(categoryId: string, index: number): string {
  const normalizedId = categoryId.toLowerCase();
  const slot = categorySlots[normalizedId] ?? (index % paletteSize) + 1;
  return `var(--chart-${slot})`;
}
