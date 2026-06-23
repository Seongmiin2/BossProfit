import { prisma } from "./prisma";

async function main() {
  await prisma.recipeItem.deleteMany();
  await prisma.menu.deleteMany();
  await prisma.ingredient.deleteMany();

  const pork = await prisma.ingredient.create({ data: { name: "돼지고기", unit: "g", unitPrice: 7 } });
  const breadCrumbs = await prisma.ingredient.create({ data: { name: "빵가루", unit: "g", unitPrice: 3.25 } });
  const cheese = await prisma.ingredient.create({ data: { name: "치즈", unit: "g", unitPrice: 23.8 } });
  const oil = await prisma.ingredient.create({ data: { name: "식용유", unit: "ml", unitPrice: 2 } });
  const udonNoodle = await prisma.ingredient.create({ data: { name: "우동면", unit: "개", unitPrice: 800 } });
  const fishCake = await prisma.ingredient.create({ data: { name: "어묵", unit: "개", unitPrice: 500 } });
  const broth = await prisma.ingredient.create({ data: { name: "우동육수", unit: "ml", unitPrice: 1.5 } });

  const kingPorkCutlet = await prisma.menu.create({ data: { name: "왕돈까스", category: "돈까스", price: 13000 } });
  const cheesePorkCutlet = await prisma.menu.create({ data: { name: "치즈돈까스", category: "돈까스", price: 15000 } });
  const udon = await prisma.menu.create({ data: { name: "즉석우동", category: "우동", price: 8000 } });
  const fishCakeUdon = await prisma.menu.create({ data: { name: "어묵우동", category: "우동", price: 9000 } });

  await prisma.recipeItem.createMany({
    data: [
      { menuId: kingPorkCutlet.id, ingredientId: pork.id, quantity: 200 },
      { menuId: kingPorkCutlet.id, ingredientId: breadCrumbs.id, quantity: 80 },
      { menuId: kingPorkCutlet.id, ingredientId: oil.id, quantity: 100 },
      { menuId: cheesePorkCutlet.id, ingredientId: pork.id, quantity: 200 },
      { menuId: cheesePorkCutlet.id, ingredientId: breadCrumbs.id, quantity: 80 },
      { menuId: cheesePorkCutlet.id, ingredientId: cheese.id, quantity: 80 },
      { menuId: cheesePorkCutlet.id, ingredientId: oil.id, quantity: 100 },
      { menuId: udon.id, ingredientId: udonNoodle.id, quantity: 1 },
      { menuId: udon.id, ingredientId: broth.id, quantity: 500 },
      { menuId: fishCakeUdon.id, ingredientId: udonNoodle.id, quantity: 1 },
      { menuId: fishCakeUdon.id, ingredientId: broth.id, quantity: 500 },
      { menuId: fishCakeUdon.id, ingredientId: fishCake.id, quantity: 2 },
    ],
  });

  console.log("Seed data inserted.");
}

main()
  .catch((error) => {
    console.error(error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
