import express from "express";
import path from "path";
import { ingredientRouter } from "./routes/ingredient.routes";
import { menuRouter } from "./routes/menu.routes";
import { recipeItemRouter } from "./routes/recipe-item.routes";

const app = express();
const port = 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, "..", "public")));

app.get("/api", (_req, res) => {
  res.json({
    service: "BOSS PROFIT - Menu Cost API",
    endpoints: [
      "GET /api/menus",
      "GET /api/menus/:id",
      "GET /api/menus/:id/cost",
      "GET /api/ingredients",
      "GET /api/recipe-items",
      "POST /api/recipe-items",
    ],
  });
});

app.use("/api/menus", menuRouter);
app.use("/api/ingredients", ingredientRouter);
app.use("/api/recipe-items", recipeItemRouter);

app.listen(port, () => {
  console.log(`BOSS PROFIT API server is running on http://localhost:${port}`);
});
