import sys
import os
from glob import glob
repo_dir = os.path.dirname(__file__)
verbose = "-v" in sys.argv

def to_number(s, multiplier=1):
    num = None
    if type(s) is str: 
        s = s.strip()
        if not s: return None
        if '/' in s:
            num, denom = s.split('/')
            num = float(num) / float(denom)
    if num is None: num = float(s)
    num *= multiplier
    if int(num) == num:
        return int(num)
    return num

def table_to_dict(table_str):
    lines = [line.strip() for line in table_str.strip().split("\n") if line.strip()]
    headers = [h.strip().lower() for h in lines[0].split('|') if h.strip()]
    data = []
    for line in lines[2:]:
        values = [v.strip() for v in line.split('|') if v.strip()]
        entry = {headers[i]: values[i] for i in range(len(headers))}
        data.append(entry)
    return data

unit_conversions = [
    {"cup":1,"ml":236.588,"tbsp":16,"tsp":48,"oz":8,"l":0.236588,"pt":0.5,"qt":0.25,"gal":0.0625},
    {"g":1,"kg":0.001,"oz":0.035274,"lb":0.0022046249999752}
]

class Ingredient:
    def __init__(self,data):
        name = data["ingredient"].split("[[")[1].split("]]")[0].split("|")[0]
        self.row = f"| {' | '.join(str(data[key]) for key in data)} |"
        self.quantity = to_number(data["quantity"])
        self.unit = data["unit"].strip().lower()
        
        ingredient_dir = os.path.join(repo_dir, "Ingredients")
        self.name = name.strip()
        if os.path.isfile(os.path.join(ingredient_dir, f"{self.name}.md")):
            self.file = os.path.join(ingredient_dir, f"{self.name}.md")
            self.category = None
        else:
            try: 
                self.file = glob(os.path.join(ingredient_dir, os.path.join("*",f"{self.name}*.md")))[0]
                self.category = os.path.basename(os.path.dirname(self.file))
            except IndexError: raise ValueError(f"Ingredient '{self.name}' not found in Ingredients directory.")
        
        with open(self.file, 'r') as file:
            self.content = file.read()
        
        # Parse serving sizes
        serving_sizes = table_to_dict(self.content.split("#### Serving Size:")[1].split("#### Notes")[0].strip())
        self.serving_sizes = {}
        for entry in serving_sizes:
            if any(entry["unit"] in measurement_type for measurement_type in unit_conversions):
                for measurement_type in unit_conversions:
                    if entry['unit'] in measurement_type:
                        for unit in measurement_type:
                            self.serving_sizes[unit] = to_number(entry['number'], measurement_type[unit] / measurement_type[entry['unit']])
                        break
            else:
                self.serving_sizes[entry['unit']] = to_number(entry['number'])
        
        # Parse nutrition facts
        nutrition_facts_lines = self.content.split("---\n")[1].strip().split("\n")
        self.nutrition_facts = {}
        self.dietary_restrictions = {}
        for line in nutrition_facts_lines:
            if "(" in line:
                self.nutrition_facts[line.split(":")[0]] = to_number(line.split(":")[1], self.quantity / self.serving_sizes[self.unit])
            else:
                self.dietary_restrictions[line.split(":")[0]] = line.split(":")[1].strip()
        
        if verbose:
            print(self.name)
            print(self.nutrition_facts)
    
    def __hash__(self):
        return hash(self.nutrition_facts)
    def __eq__(self, other):
        return self.nutrition_facts == other.nutrition_facts
            
class Recipe:
    def __init__(self, name):
        self.name = name
        self.file = os.path.join(os.path.join(repo_dir,"Recipes"), f"{self.name}.md")
        
        with open(self.file, 'r') as file:
            self.content = file.read()
        
        ingredients = table_to_dict(self.content.split("#### Ingredients")[1].split("####")[0].strip())
        self.ingredients = [Ingredient(entry) for entry in ingredients if "[[" in entry["ingredient"]]
        
        # Sum nutrition facts
        nutrition_facts = {
            "Calories (kcal)":          None,
            "Total Fat (g)":            None,
            "Saturated Fat (g)":        None,
            "Trans Fat (g)":            None,
            "Cholesterol (mg)":         None,
            "Sodium (mg)":              None,
            "Total Carbohydrate (g)":   None,
            "Dietary Fiber (g)":        None,
            "Sugars (g)":               None,
            "Protein (g)":              None
        }
        self.dietary_restrictions = {
            "Gluten Free": True,
            "Dairy Free": True,
            "Vegan": True
        }
        for ingredient in self.ingredients:
            for key in nutrition_facts:
                macro = ingredient.nutrition_facts.get(key, None)
                if nutrition_facts[key] is None:
                    nutrition_facts[key] = ingredient.nutrition_facts.get(key, None)
                elif macro is not None: nutrition_facts[key] += ingredient.nutrition_facts.get(key, 0)
            for key in self.dietary_restrictions:
                if ingredient.dietary_restrictions.get(key, "false") == "false": 
                    self.dietary_restrictions[key] = False
        
        self.nutrition_facts ={}
        for key in nutrition_facts:
            if nutrition_facts[key] is not None:
                if "(g)" in key:
                    # Round to nearest 0.5g
                    self.nutrition_facts[key] = to_number(round(nutrition_facts[key]*2)/2)
                else:
                    # Round to nearest mg or kcal
                    self.nutrition_facts[key] = int(round(nutrition_facts[key]))
        self.high_protein = False
        try:
            if self.nutrition_facts["Calories (kcal)"] < 10*self.nutrition_facts["Protein (g)"]: self.high_protein = True
        except TypeError: pass
        
    def write(self):
        content = self.content
        
        # Update diet tags
        tags = {
            "Calorie range": None,
            "High Protein": f"{self.high_protein}".lower(),
            "Gluten Free": f"{self.dietary_restrictions.get('Gluten Free', 'false')}".lower(),
            "Dairy Free": f"{self.dietary_restrictions.get('Dairy Free', 'false')}".lower(),
            "Vegan": f"{self.dietary_restrictions.get('Vegan', 'false')}".lower()
        }
        if self.nutrition_facts["Calories (kcal)"] < 200:
            tags["Calorie range"] = "<200"
        elif self.nutrition_facts["Calories (kcal)"] >= 600: 
            tags["Calorie range"] = "600+"
        else:
            tags["Calorie range"] = f"{(self.nutrition_facts['Calories (kcal)']//100)*100}-{(self.nutrition_facts['Calories (kcal)']//100)*100+99}"
        for tag in tags:
            content = content.replace(
                f"{tag}:" + content.split(f"{tag}:")[1].split("\n")[0],
                f"{tag}: {tags[tag]}"
            )
        # Update nutrition facts
        nutrition_facts = [f"| {key} | {self.nutrition_facts[key]} |" for key in self.nutrition_facts]
        nutrition_facts.insert(1, "| :-- | :--: |")
        content = content.replace(
            "#### Nutrition Facts" + self.content.split("#### Nutrition Facts")[1].split("####")[0],
            f"#### Nutrition Facts\n" + "\n".join(nutrition_facts) + "\n"
        )
        # Respace ingredients
        content = content.replace(
            "#### Ingredients" + self.content.split("#### Ingredients")[1].split("####")[0],
            f"#### Ingredients\n| Quantity | Unit | Ingredient |\n| :--: | :--: | :--- |\n" + "\n".join(i.row for i in self.ingredients) + "\n"
        )
        with open(self.file,"w") as fo:
            fo.write(content)

if __name__ == "__main__":
    for recipe in glob(os.path.join(repo_dir, "Recipes", "*.md")):
        recipe_name = os.path.basename(recipe).split(".md")[0]    
        Recipe(recipe_name).write()