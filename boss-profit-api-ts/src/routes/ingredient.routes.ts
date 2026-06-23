import { Router } from "express";
import { prisma } from "../prisma";

export const ingredientRouter = Router();

ingredientRouter.get("/", async (_req, res) => {
  const ingredients = await prisma.ingredient.findMany({
    orderBy: { id: "asc" },
  });

  res.json(ingredients);
});
