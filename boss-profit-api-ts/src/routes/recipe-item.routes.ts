import { Router } from "express";
import { prisma } from "../prisma";

export const recipeItemRouter = Router();

recipeItemRouter.get("/", async (_req, res) => {
  const recipeItems = await prisma.recipeItem.findMany({
    include: {
      menu: true,
      ingredient: true,
    },
    orderBy: { id: "asc" },
  });

  res.json(recipeItems);
});

recipeItemRouter.post("/", async (req, res) => {
  const { menuId, ingredientId, quantity } = req.body;

  if (!menuId || !ingredientId || quantity === undefined) {
    return res.status(400).json({ message: "menuId, ingredientId, quantity are required" });
  }

  try {
    const recipeItem = await prisma.recipeItem.create({
      data: {
        menuId: Number(menuId),
        ingredientId: Number(ingredientId),
        quantity: Number(quantity),
      },
    });

    return res.status(201).json(recipeItem);
  } catch (_error) {
    return res.status(400).json({ message: "failed to create recipe item" });
  }
});
