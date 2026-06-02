import { Router } from "express";
import { prisma } from "../prisma";
import { calculateMenuCost } from "../services/cost.service";

export const menuRouter = Router();

menuRouter.get("/", async (_req, res) => {
  const menus = await prisma.menu.findMany({
    orderBy: { id: "asc" },
  });

  res.json(menus);
});

menuRouter.get("/:id", async (req, res) => {
  const id = Number(req.params.id);

  if (Number.isNaN(id)) {
    return res.status(400).json({ message: "id must be a number" });
  }

  const menu = await prisma.menu.findUnique({
    where: { id },
    include: {
      recipeItems: {
        include: { ingredient: true },
      },
    },
  });

  if (!menu) {
    return res.status(404).json({ message: "menu not found" });
  }

  res.json(menu);
});

menuRouter.get("/:id/cost", async (req, res) => {
  const id = Number(req.params.id);

  if (Number.isNaN(id)) {
    return res.status(400).json({ message: "id must be a number" });
  }

  const result = await calculateMenuCost(id);

  if (!result) {
    return res.status(404).json({ message: "menu not found" });
  }

  res.json(result);
});
