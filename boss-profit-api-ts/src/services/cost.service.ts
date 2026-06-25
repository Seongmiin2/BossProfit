import { prisma } from "../prisma";

export async function calculateMenuCost(menuId: number) {
  const menu = await prisma.menu.findUnique({
    where: { id: menuId },
    include: {
      recipeItems: {
        include: { ingredient: true },
        orderBy: { id: "asc" },
      },
    },
  });

  if (!menu) {
    return null;
  }

  const items = menu.recipeItems.map((item) => {
    const cost = item.quantity * item.ingredient.unitPrice;

    return {
      ingredient: item.ingredient.name,
      quantity: item.quantity,
      unit: item.ingredient.unit,
      unit_price: item.ingredient.unitPrice,
      cost: Math.round(cost),
    };
  });

  const totalCost = items.reduce((sum, item) => sum + item.cost, 0);
  const margin = menu.price - totalCost;
  const marginRate = menu.price === 0 ? 0 : Number(((margin / menu.price) * 100).toFixed(2));

  return {
    menu: menu.name,
    price: menu.price,
    total_cost: totalCost,
    margin,
    margin_rate: marginRate,
    items,
  };
}
