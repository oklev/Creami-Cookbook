import sys
import os
from glob import glob
repo_dir = os.path.dirname(__file__)

def main(recipe_name):
    recipe_name = os.path.basename(recipe_name).split(".md")[0]    
    Recipe(recipe_name).write()

def to_number(s):
    if type(s) is str: 
        s = s.strip()
        if not s: return 0
        if '/' in s:
            num, denom = s.split('/')
            return float(num) / float(denom)
    num = float(s)
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
                            self.serving_sizes[unit] = to_number(entry['number']) * measurement_type[unit] / measurement_type[entry['unit']]
                        break
            else:
                self.serving_sizes[entry['unit']] = to_number(entry['number'])
        
        # Parse nutrition facts
        nutrition_facts_lines = self.content.split("---\n")[1].strip().split("\n")
        self.nutrition_facts = {}
        for line in nutrition_facts_lines:
            self.nutrition_facts[line.split(":")[0]] = to_number(line.split(":")[1]) * self.quantity / self.serving_sizes[self.unit]
        
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
        self.ingredients = [Ingredient(entry) for entry in ingredients]
        
        # Sum nutrition facts
        nutrition_facts_lines = self.content.split("---\n")[1].strip().split("\n")
        self.nutrition_facts = {line.split(":")[0]: 0 for line in nutrition_facts_lines}
        for ingredient in self.ingredients:
            for key in self.nutrition_facts:
                self.nutrition_facts[key] += ingredient.nutrition_facts.get(key, 0)
        
        for key in self.nutrition_facts:
            if "(g)" in key:
                self.nutrition_facts[key] = to_number(round(self.nutrition_facts[key]*2)/2)
            else:
                self.nutrition_facts[key] = int(round(self.nutrition_facts[key]))
        
    def write(self):
        content = f"---\n"
        for key in self.nutrition_facts:
            content += f"{key}: {self.nutrition_facts[key]}\n"
        content += f"---\n"
        content += self.content.split("---\n",2)[2]
        with open(self.file,"w") as fo:
            fo.write(content)

if __name__ == "__main__":
    main(sys.argv[1])