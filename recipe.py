import sys
import os
from glob import glob
import json
repo_dir = os.path.dirname(__file__)
ingredient_dir = os.path.join(repo_dir, "Ingredients")
verbose = "-v" in sys.argv
unit_conversions = {
    "Volume":{"cup":1,"ml":236.588,"tbsp":16,"tsp":48,"fl oz":8,"l":0.236588,"pt":0.5,"qt":0.25,"gal":0.0625,"cups":1,"c":1,"T":16,"t":48,"gallon":0.0625,"pint":0.5,"quart":0.25,"fl oz":8,"fluid ounce":8},
    "Weight":{"g":1,"oz":0.035274,"gram":1,"grams":1}
}
ingredients = {}
properties = {}
property_types = {}
dietary_restrictions = (
    "Gluten Free",
    "Dairy Free",
    "Vegan"
)

def to_number(s, multiplier=1):
    if s is None: return None
    num = None
    if type(s) is str: 
        s = s.strip()
        if not s: return None
        if '/' in s:
            if " " in s: 
                whole = int(s.split(" ")[0])
                s = s.split(" ",1)[1]
            else: whole = 0
            num, denom = s.split('/')
            num = whole + float(num) / float(denom)
    if num is None: num = float(s)
    num *= multiplier
    if int(num) == num:
        return int(num)
    return num

def to_str(s):
    if s is None: return ""
    if int(s) == s: return str(int(s))
    whole = int(s)
    frac = s - whole
    conversion = {
        0:"", 1:"1",
        0.25:"1/4", 0.5:"1/2", 0.75:"3/4",
        0.3333:"1/3", 0.6667:"2/3",
        0.125:"1/8", 0.375:"3/8", 0.625:"5/8", 0.875:"7/8"
    }
    dist = {abs(frac - f):f for f in conversion}
    closest = conversion[dist[min(dist)]]
    if closest == "1": return str(whole + 1)
    elif whole == 0 and closest: return closest
    else: return f"{whole} {closest}".strip()

def to_imperial(ml):
    whole = 0
    if ml > 236:
        mod = ml % 236
        whole = int((ml-mod)/236)
        ml = mod
    conversion = {
        236:"1 cup",
        177:"3/4 cup",
        158:"2/3 cup",
        118:"1/2 cup",
        79:"1/3 cup",
        59:"1/4 cup"
    }
    if whole == 0:
        conversion.update(
            {
                44:"3 tbsp",
                37:"2 1\2 tbsp",
                30:"2 tbsp",
                22:"1 1/2 tbsp",
                15:"1 tbsp",
                11:"3/4 tbsp",
                10:"2 tsp",
                7:"1/2 tbsp",
                5:"1 tsp",
                4:"1/4 tbsp",
                2.5:"1/2 tsp",
                1.2:"1/4 tsp",
                0.6:"1/8 tsp"
            }
        )
    else:
        conversion.update(
            {0:"cup"}
        )
    dist = {abs(ml - f):f for f in conversion}
    fraction = conversion[dist[min(dist)]]
    if fraction == "1 cup":
        whole += 1
        fraction = "cup"
    if whole: fraction = f"{whole} {fraction}"
    return fraction

def to_other(amount, unit):
    rounded = round(amount*2)/2
    if rounded > 0 and rounded == int(rounded): return f"{int(rounded)} {unit}"
    if amount > 0.4 and amount < 0.6: return f"1/2 {unit}"
    if amount > 1: return f"{int(rounded)} 1/2"
    else: return ""

def table_to_dict(table_str,link_required=False):
    lines = [line.strip() for line in table_str.strip().split("\n") if line.strip()]
    lines.pop(1)
    table = []
    for line in lines:
        line = line[1:-1].split("[[")
        if len(line) > 1 or not link_required:
            links = []
            for i in range(1,len(line)):
                links.append(line[i].split("]]")[0])
                line[i] = f"[[{len(links)-1}]]{line[i].split(']]')[1]}"
            line = "".join(line).split("|")
            for v,value in enumerate(line):
                if "[[" in value:
                    i = int(value.split("[[")[1].split("]]")[0])
                    value = value.replace(f"[[{i}]]",f"[[{links[i]}]]")
                line[v] = value.strip()
            table.append(line)
    headers = [h.lower() for h in table.pop(0)]
    return [{category: values[v] for v,category in enumerate(headers)} for values in table]

class Boolean:
    def __init__(self, s=False):
        if type(s) is str: 
            if s.lower() == "true": self.value = True
            else: self.value = False
        else: self.value = bool(s)
    def __str__(self):
        return "true" if self.value else "false"
    def __repr__(self):
        return str(self)
    def __bool__(self):
        return self.value
    def _set(self, b):
        self.value = bool(b)
    def _or(self, b):
        self.value = self.value or bool(b)
    def _and(self, b):
        self.value = self.value and bool(b)

class Number:
    def __init__(self, s):
        self.value = to_number(s)
    def __str__(self):
        return to_str(self.value)
    def __repr__(self):
        return str(self)
    def __float__(self):
        return self.value
    def __int__(self):
        return int(self.value)

class Ingredient:
    def __init__(self,file):
        self.file = file
        self.name = os.path.basename(file).split(".md")[0]
        self.category = os.path.basename(os.path.dirname(file))
        if self.category == "Ingredients": self.category = None
        self.volume = False
        self.weight = False
        self.other = None
        
        with open(self.file, 'r') as file:
            self.content = file.read()
        
        # Parse serving sizes
        serving_sizes = table_to_dict(self.content.split("#### Serving Size:")[1].split("#### Notes")[0].strip())
        self.serving_sizes = {}
        for entry in serving_sizes:
            if entry["unit"] in unit_conversions["Volume"]:
                measurement_type = "Volume"
                self.volume = True
            elif entry["unit"] in unit_conversions["Weight"]:
                measurement_type = "Weight"
                self.weight = True
            else: 
                measurement_type = "Other"
                self.other = entry["unit"]
            if measurement_type == "Other":
                self.serving_sizes[entry["unit"]] = to_number(entry["number"])
            else:
                for unit in unit_conversions[measurement_type]:
                    self.serving_sizes[unit] = to_number(entry["number"], unit_conversions[measurement_type][unit] / unit_conversions[measurement_type][entry["unit"]])
        # Use weight of water to approx weight of liquids
        if not self.weight and "ml" in self.serving_sizes:
            self.serving_sizes["g"] = self.serving_sizes["ml"]
            self.weight = True
        
        # Parse nutrition facts
        nutrition_facts_lines = self.content.split("---\n")[1].strip().split("\n")
        self.nutrition_facts = {}
        self.dietary_restrictions = {}
        for line in nutrition_facts_lines:
            if "(" in line:
                self.nutrition_facts[line.split(":")[0]] = to_number(line.split(":")[1])
            else:
                self.dietary_restrictions[line.split(":")[0]] = Boolean(line.split(":")[1].strip())
        
        if verbose:
            print(self.name)
            print(self.nutrition_facts)
    
    def get_nutrition(self, factor):
        nutrition = {key:to_number(self.nutrition_facts[key], factor) for key in self.nutrition_facts}
        return nutrition
    
    def amount(self,quantity,unit):
        if unit not in self.serving_sizes:
            raise ValueError(f"Unit '{unit}' not found for ingredient '{self.name}'. Available units: {', '.join(self.serving_sizes.keys())}")
        return quantity / self.serving_sizes[unit]
    
    def line(self,factor,description, calories=False):
        line = f"| {description} |"
        if calories:
            line += f" {int(round(self.nutrition_facts['Calories (kcal)']*factor))} |"
        if self.volume: line += f" {to_imperial(self.serving_sizes['ml']*factor)} |"
        else: line += " |"
        if self.weight: 
            if self.serving_sizes["g"] < 10:
                line += f" {to_number(round(self.serving_sizes['g']*factor*2)/2)} g |"
            elif self.serving_sizes["g"] < 100:
                line += f" {int(round(self.serving_sizes['g']*factor))} g |"
            else:
                line += f" {int(round(self.serving_sizes['g']*factor,-1))} g |"        
        else: line += " |"
        if self.other:  line += f" {to_other(self.serving_sizes[self.other]*factor,self.other)} |"
        else: line += " |"
        return line
    
    def __hash__(self):
        return hash(self.nutrition_facts)
    def __eq__(self, other):
        return self.nutrition_facts == other.nutrition_facts
            
class Recipe:
    def __init__(self, name):
        self.name = name
        self.file = os.path.join(os.path.join(repo_dir,"Recipes"), f"{self.name}.md")
        self.properties = {key:property_types[key](properties[key]) for key in properties}
        
        with open(self.file, 'r') as file:
            content = file.read()
            for line in content.split("---\n")[1].strip().split("\n"):
                if ":" in line:
                    key = line.split(":")[0].strip()
                    if key in dietary_restrictions: self.properties[key] = Boolean(True)
                    else:
                        value = line.split(":",1)[1].strip()
                        self.properties[key] = property_types[key](value)
            if "## Base Recipe" in content:
                self.content = content.rsplit("## Base Recipe",1)[1].strip()
                if "\n## " in self.content:
                    self.content = self.content.split("\n## ")[0].strip()
            else:
                self.content = content.split("---\n",2)[2].strip()
        if "Volume" in properties:
            self.volume = to_number(properties.split("Volume:")[1].split("\n")[0].strip())
        else:
            self.volume = None
        
        # Get list of ingredients
        self.ingredients = {}
        ingredients_text = self.content.split("#### Ingredients")[1].split("####")[0].strip()
        if "| Unit |" in ingredients_text:
            def get_unit(entry):
                return entry["unit"].strip().lower()
            def get_quantity(entry):
                return entry["quantity"]
        else:
            def get_unit(entry):
                if len(entry["other"].strip().split()) == 2:
                    return entry["other"].strip().split()[-1]
                if entry["volume"]: return entry["volume"].strip().split()[-1]
                if entry["weight"]: return "g"
                return entry["other"].strip().split()[-1]
            def get_quantity(entry):
                if len(entry["other"].strip().split()) == 2:
                    return entry["other"].strip().split(maxsplit=1)[0]
                if entry["volume"]: return entry["volume"].strip().rsplit(maxsplit=1)[0]
                if entry["weight"]: return entry["weight"].replace("g","").strip()
                return entry["other"].strip().split(maxsplit=1)[0]
        for entry in table_to_dict(ingredients_text):
            if "[[" in entry["ingredient"]: i = entry["ingredient"].split("[[")[1].split("]]")[0].split("|")[0].strip()
            else: i = entry["ingredient"].strip()
            self.ingredients[i] = (
                ingredients[i].amount(to_number(get_quantity(entry)), get_unit(entry)), entry["ingredient"].strip()
            )
        
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
        for ingredient in self.ingredients:
            if ingredient in ingredients:
                ingredient_nutrition = ingredients[ingredient].get_nutrition(self.ingredients[ingredient][0])
                ingredient = ingredients[ingredient]
                for key in nutrition_facts:
                    macro = ingredient_nutrition.get(key, None)
                    if nutrition_facts[key] is None:
                        nutrition_facts[key] = macro
                    elif macro is not None: nutrition_facts[key] += macro
                for key in dietary_restrictions:
                    self.properties[key]._and(Boolean(ingredient.dietary_restrictions.get(key, False)))
        
        self.nutrition_facts ={}
        for key in nutrition_facts:
            if nutrition_facts[key] is not None:
                if "(g)" in key:
                    # Round to nearest 0.5g
                    self.nutrition_facts[key] = to_number(round(nutrition_facts[key]*2)/2)
                else:
                    # Round to nearest mg or kcal
                    self.nutrition_facts[key] = int(round(nutrition_facts[key]))
        self.properties["High Protein"] = Boolean()
        try:
            if self.nutrition_facts["Calories (kcal)"] < 10*self.nutrition_facts["Protein (g)"]: self.properties["High Protein"]._set(True)
        except TypeError: pass
        
        if self.nutrition_facts["Calories (kcal)"] < 200:
            self.properties["Calorie range"] = "<200"
        elif self.nutrition_facts["Calories (kcal)"] >= 600: 
            self.properties["Calorie range"] = "600+"
        else:
            self.properties["Calorie range"] = f"{(self.nutrition_facts['Calories (kcal)']//100)*100}-{(self.nutrition_facts['Calories (kcal)']//100)*100+99}"
        
    def write(self):
        content = "---\n" + "\n".join(f"{key}: {self.properties[key]}" for key in self.properties) + f"\n---\n## Base Recipe\n{self.content}"
        
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
            f"#### Ingredients\n| Ingredient | Calories | Volume | Weight | Other |\n| :-- | :--: | :--: | :--: | :--: |\n" + 
                "\n".join(ingredients[i].line(*self.ingredients[i],calories=True) for i in self.ingredients) + "\n"
        )
        with open(self.file,"w") as fo:
            fo.write(content)

if __name__ == "__main__":
    for ingredient in glob(os.path.join(ingredient_dir, "**", "*.md")):
        ingredient = Ingredient(ingredient)
        ingredients[ingredient.name] = ingredient
    with open(os.path.join(repo_dir, "Templates","Recipe.md")) as file:
        content = file.read()
        for line in content.split("---")[1].strip().split("\n"):
            if ":" in line:
                key = line.split(":")[0].strip()
                value = line.split(":",1)[1].strip()
                properties[key] = value
    with open(os.path.join(repo_dir, ".obsidian","types.json")) as file:
        json_properties = json.load(file)["types"]
        for prop in properties:
            if prop in json_properties:
                if json_properties[prop] == "number":
                    property_types[prop] = Number
                elif json_properties[prop] == "checkbox":
                    property_types[prop] = Boolean
                else: property_types[prop] = str
            else:
                property_types[prop] = str
    
    for recipe in glob(os.path.join(repo_dir, "Recipes", "*.md")):
        recipe_name = os.path.basename(recipe).split(".md")[0]    
        Recipe(recipe_name).write()