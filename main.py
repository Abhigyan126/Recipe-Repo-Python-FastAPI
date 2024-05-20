from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# MongoDB connection
mongo_url = ""
client = AsyncIOMotorClient(mongo_url)
db = client.mydatabase


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up templates
templates = Jinja2Templates(directory="templates")

@app.get("/insert", response_class=HTMLResponse)
async def read_insert(request: Request):
    return templates.TemplateResponse("insert.html", {"request": request})

# Define Pydantic models
class RecipeModel(BaseModel):
    title: str
    alias: str
    ingredients: List[str]
    instructions: str
    ratings: Optional[float] = 0
    ratingCount: Optional[int] = 0

class UpdateRecipeModel(BaseModel):
    title: Optional[str]
    alias: Optional[str]
    ingredients: Optional[List[str]]
    instructions: Optional[str]

class RateRecipeModel(BaseModel):
    rating: int



@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/recipes", response_description="Add new recipe")
async def create_recipe(recipe: RecipeModel):
    if await db.recipes.find_one({"title": recipe.title}):
        raise HTTPException(status_code=400, detail="Recipe with the same title already exists")
    new_recipe = recipe.dict()
    new_recipe["createdAt"] = str(ObjectId().generation_time)
    await db.recipes.insert_one(new_recipe)
    return new_recipe

@app.get("/recipes", response_description="List all recipes")
async def list_recipes(search: Optional[str] = None):
    query = {}
    if search:
        query = {"$or": [
            {"title": {"$regex": search, "$options": "i"}},
            {"ingredients": {"$regex": search, "$options": "i"}}
        ]}
    recipes = await db.recipes.find(query).sort("createdAt", -1).to_list(1000)
    return recipes

@app.put("/recipes/{id}", response_description="Update a recipe")
async def update_recipe(id: str, recipe: UpdateRecipeModel):
    if (existing_recipe := await db.recipes.find_one({"_id": ObjectId(id)})) is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    await db.recipes.update_one({"_id": ObjectId(id)}, {"$set": recipe.dict(exclude_unset=True)})
    return await db.recipes.find_one({"_id": ObjectId(id)})

@app.patch("/recipes/{id}", response_description="Rate a recipe")
async def rate_recipe(id: str, rate: RateRecipeModel):
    if (recipe := await db.recipes.find_one({"_id": ObjectId(id)})) is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if not 1 <= rate.rating <= 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    new_rating_count = recipe["ratingCount"] + 1
    new_ratings = (recipe["ratings"] * recipe["ratingCount"] + rate.rating) / new_rating_count
    await db.recipes.update_one({"_id": ObjectId(id)}, {"$set": {"ratings": new_ratings, "ratingCount": new_rating_count}})
    updated_recipe = await db.recipes.find_one({"_id": ObjectId(id)})
    return {"recipe": updated_recipe, "averageRating": new_ratings}

@app.delete("/recipes/{id}", response_description="Delete a recipe")
async def delete_recipe(id: str):
    if (recipe := await db.recipes.find_one({"_id": ObjectId(id)})) is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    await db.recipes.delete_one({"_id": ObjectId(id)})
    return {"message": "Recipe deleted"}

@app.post("/recipes/share/{id}", response_description="Share a recipe")
async def share_recipe(id: str):
    if (recipe := await db.recipes.find_one({"_id": ObjectId(id)})) is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    recipe_link = f"https://yourdomain.com/recipes/{id}"
    return {"message": "Recipe shared successfully", "recipeLink": recipe_link}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
