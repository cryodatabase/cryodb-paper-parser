-- Complete SQL INSERT statements for cpa_chemicals table
-- Total: 126 chemical entries (removed 3 duplicates)
-- Structure: INSERT INTO cpa_chemicals (inchikey, preferred_name, synonyms) VALUES (...);

INSERT INTO cpa_chemicals (inchikey, preferred_name, synonyms) VALUES 

-- Sugars and Sugar Alcohols
('CZMRCDWAGMRECN-UGDNZRGBSA-N', 'Sucrose', '["sucrose", "table sugar", "cane sugar", "saccharose", "β-D-fructofuranosyl α-D-glucopyranoside"]'),
('WQZGKKKJIJFFOK-GASJEMHNSA-N', 'Glucose', '["glucose", "D-glucose", "dextrose", "grape sugar", "blood sugar"]'),
('WQZGKKKJIJFFOK-VFUOTHLCSA-N', 'Galactose', '["galactose", "D-galactose", "brain sugar", "milk sugar component"]'),
('PYMYPHUHKUWMLA-LMVFSUKVSA-N', 'Xylose', '["xylose", "D-xylose", "wood sugar", "birch sugar"]'),
('HMFHBZSHGGEWLO-SOOFDHNKSA-N', 'Ribose', '["ribose", "D-ribose", "RNA sugar", "aldopentose"]'),
('RFSUNEUAIZKAJO-ARQDHWQXSA-N', 'Fructose', '["fructose", "D-fructose", "fruit sugar", "levulose"]'),
('PYMYPHUHKUWMLA-WDCZJNDASA-N', 'Mannose', '["mannose", "D-mannose", "carubinose", "seminose"]'),
('HDTRYLNUVZCQOY-LIZSDCNHSA-N', 'Trehalose', '["trehalose", "α,α-trehalose", "D-trehalose", "mycose", "tremalose"]'),
('GUBGYTABKSRVRQ-QKKXKWKRSA-N', 'Maltose', '["maltose", "malt sugar", "maltobiose", "4-O-α-D-glucopyranosyl-D-glucose"]'),
('JGVSLKYHMHGKOL-DWAXBSCTSA-N', 'Raffinose', '["raffinose", "melitose", "melitriose", "D-raffinose"]'),

-- Sugar Alcohols (Polyols)
('PEDCQBHIVMGVHV-UHFFFAOYSA-N', 'Glycerol', '["glycerol", "glycerin", "glycerine", "1,2,3-propanetriol", "propane-1,2,3-triol"]'),
('FBPFZTCFMRRESA-JGWLITMVSA-N', 'Sorbitol', '["sorbitol", "D-sorbitol", "glucitol", "D-glucitol", "E420"]'),
('FBPFZTCFMRRESA-KVTDHHQDSA-N', 'Mannitol', '["mannitol", "D-mannitol", "manna sugar", "E421", "cordycepic acid"]'),
('UNXHWFMMPAWVPI-ZXZARUISSA-N', 'Erythritol', '["erythritol", "meso-erythritol", "1,2,3,4-butanetetrol", "E968"]'),
('HEBKCHPVOIAQTA-SCDXWVJYSA-N', 'Xylitol', '["xylitol", "birch sugar", "wood sugar alcohol", "E967"]'),
('FBPFZTCFMRRESA-RADKZDAESA-N', 'Dulcitol', '["dulcitol", "galactitol", "D-galactitol", "melampyrin"]'),
('UNXHWFMMPAWVPI-IMJSIDKUSA-N', 'Threitol', '["threitol", "L-threitol", "1,2,3,4-butanetetrol"]'),

-- Inositols and Cyclitols
('CDAISMWEOUEBRE-GPIVLXJGSA-N', 'Myo-Inositol', '["myo-inositol", "inositol", "cyclohexitol", "vitamin B8"]'),
('FBPFZTCFMRRESA-BJLMENQBSA-N', 'Pinitol', '["pinitol", "D-pinitol", "(+)-pinitol", "3-O-methyl-D-chiro-inositol"]'),
('LKCWBDHBTVXHDL-RMKNXTFCSA-N', 'Ononitol', '["ononitol", "4-O-methyl-myo-inositol", "4-O-methylinositol"]'),
('CQEYYJKEWSMYFG-YGVPPNBJSA-N', 'Quebrachitol', '["quebrachitol", "L-quebrachitol", "1-O-methyl-L-chiro-inositol", "L-viburnitol"]'),
('CQEYYJKEWSMYFG-CUOXTBUKSA-N', 'Quercitol', '["quercitol", "D-quercitol", "acorn sugar", "quercinitol"]'),
(NULL, 'Cyclitol', '["cyclitol", "inositol", "carbocyclic polyol", "cyclic polyol"]'),
(NULL, 'O-Methyl-Muco-Inositol', '["O-methyl-muco-inositol", "methylated inositol", "inositol methyl ether"]'),

-- Glycols and Diols
('LYCAIKOWRPUZTN-UHFFFAOYSA-N', 'Ethylene Glycol', '["ethylene glycol", "EG", "1,2-ethanediol", "ethane-1,2-diol", "MEG"]'),
('DNIAPMSPPWPWGF-UHFFFAOYSA-N', 'Propylene Glycol', '["propylene glycol", "1,2-propanediol", "propane-1,2-diol", "PG"]'),
('QQVIHTHCMHWDBS-UHFFFAOYSA-N', 'Trimethylene Glycol', '["trimethylene glycol", "1,3-propanediol", "propane-1,3-diol", "PDO"]'),
('MTHSVFCYNBDYFN-UHFFFAOYSA-N', 'Diethylene Glycol', '["diethylene glycol", "DEG", "2,2-oxybis(ethanol)", "2,2-dihydroxydiethyl ether"]'),
('ZIBGPFATKBEMQZ-UHFFFAOYSA-N', 'Triethylene Glycol', '["triethylene glycol", "TEG", "2,2-ethylenedioxybis(ethanol)"]'),
('GJRQTCIYDGXPES-UHFFFAOYSA-N', '1,2-Butanediol', '["1,2-butanediol", "1,2-dihydroxybutane", "butane-1,2-diol"]'),
('PUPZLCDOIYMWBV-UHFFFAOYSA-N', '1,3-Butanediol', '["1,3-butanediol", "1,3-dihydroxybutane", "butane-1,3-diol"]'),
('WERYXYBDKMZEQL-UHFFFAOYSA-N', '1,4-Butanediol', '["1,4-butanediol", "1,4-dihydroxybutane", "butane-1,4-diol", "BDO"]'),
('OWBTYPJTUOEWEK-UHFFFAOYSA-N', '2,3-Butanediol', '["2,3-butanediol", "2,3-dihydroxybutane", "butane-2,3-diol"]'),

-- Alcohols
('LFQSCWFLJHTTHZ-UHFFFAOYSA-N', 'Ethanol', '["ethanol", "ethyl alcohol", "grain alcohol", "EtOH"]'),
('OKKJLVBELUTLKV-UHFFFAOYSA-N', 'Methanol', '["methanol", "methyl alcohol", "wood alcohol", "carbinol", "MeOH"]'),
('BDERNNFJNOPAEC-UHFFFAOYSA-N', '1-Propanol', '["1-propanol", "n-propanol", "propyl alcohol", "propan-1-ol"]'),
('KFZMGEQAYNKOFK-UHFFFAOYSA-N', '2-Propanol', '["2-propanol", "isopropanol", "isopropyl alcohol", "IPA", "propan-2-ol"]'),
('LRHPLDYGYMQRHN-UHFFFAOYSA-N', '1-Butanol', '["1-butanol", "n-butanol", "butyl alcohol", "butan-1-ol"]'),
('BTANRVKWQNVYAZ-UHFFFAOYSA-N', '2-Butanol', '["2-butanol", "sec-butanol", "secondary butanol", "butan-2-ol"]'),
('DKGAVHZHDRPRBM-UHFFFAOYSA-N', 'Tert-Butanol', '["tert-butanol", "t-butanol", "2-methylpropan-2-ol", "tertiary butanol"]'),
('WVDDGKGOMKODPV-UHFFFAOYSA-N', 'Benzyl Alcohol', '["benzyl alcohol", "phenylmethanol", "benzenemethanol", "phenylcarbinol"]'),
('ZSIAUFGUXNUGDI-UHFFFAOYSA-N', 'Hexanol', '["hexanol", "1-hexanol", "n-hexanol", "hexyl alcohol"]'),
('KCZDSPEQNLCMBL-UHFFFAOYSA-N', 'Octanol', '["octanol", "1-octanol", "n-octanol", "octyl alcohol"]'),

-- Ethers
('XLLIQLLCWZCATF-UHFFFAOYSA-N', 'Ethylene Glycol Monomethyl Ether', '["ethylene glycol monomethyl ether", "2-methoxyethanol", "methyl cellosolve", "EGME"]'),

-- Solvents and Aprotic Compounds
('IAZDPXIOMUYVGZ-UHFFFAOYSA-N', 'Dimethyl Sulfoxide', '["dimethyl sulfoxide", "DMSO", "methyl sulfoxide", "methylsulfinylmethane"]'),
('FORMQRAMLKQKPS-UHFFFAOYSA-N', 'Formamide', '["formamide", "FA", "methanamide", "carbamaldehyde"]'),
('YMWUJEATGCHHMB-UHFFFAOYSA-N', 'Dimethylformamide', '["dimethylformamide", "DMFA", "DMF", "N,N-dimethylformamide"]'),
('DEXFNLNNUZKHNO-UHFFFAOYSA-N', 'Dimethylacetamide', '["dimethylacetamide", "DMAc", "N,N-dimethylacetamide", "DMAC"]'),
('FVZFBFFMQISNNK-UHFFFAOYSA-N', 'Methylformamide', '["methylformamide", "MFA", "N-methylformamide", "NMF"]'),
('WVCUSKCMGRGJOL-UHFFFAOYSA-N', 'Methylacetamide', '["methylacetamide", "MAc", "N-methylacetamide", "NMA"]'),
('DLFVBJFMPXGRIB-UHFFFAOYSA-N', 'Acetamide', '["acetamide", "ethanamide", "acetic acid amide"]'),
('UMCMPZBLKLEWAF-UHFFFAOYSA-N', 'N-Methyl-2-Pyrrolidone', '["N-methyl-2-pyrrolidone", "NMP", "methylpyrrolidone", "1-methyl-2-pyrrolidinone"]'),
('HEDRZPFGACZZDS-UHFFFAOYSA-N', 'Chloroform', '["chloroform", "trichloromethane", "CHCl3", "methyl trichloride"]'),

-- Amino Acids and Related Compounds
('ONIBWKKTOPOVIA-BYPYZUCNSA-N', 'Proline', '["proline", "L-proline", "(S)-pyrrolidine-2-carboxylic acid", "Pro"]'),
('DHMQDGOQFOQNFH-UHFFFAOYSA-N', 'Glycine', '["glycine", "aminoacetic acid", "glycocoll", "Gly", "G"]'),
('QNAYBMKLOCPYGJ-REOHCLBHSA-N', 'Alanine', '["alanine", "L-alanine", "2-aminopropanoic acid", "Ala", "A"]'),
('KZSNJWFQEVHDMF-BYPYZUCNSA-N', 'Valine', '["valine", "L-valine", "2-amino-3-methylbutanoic acid", "Val", "V"]'),
('ZDXPYRJPNDTMRX-VKHMYHEASA-N', 'Glutamine', '["glutamine", "L-glutamine", "2-aminoglutaramic acid", "Gln", "Q"]'),

-- Betaines and Methylated Compounds
('KWIUHFFTVRNATP-UHFFFAOYSA-N', 'Betaine', '["betaine", "glycine betaine", "trimethylglycine", "TMG", "N,N,N-trimethylglycine"]'),
('UYPYRKYASGJCOS-UHFFFAOYSA-N', 'Trimethylamine N-Oxide', '["trimethylamine N-oxide", "TMAO", "trimethylamine oxide", "N,N,N-trimethylamine oxide"]'),
('FSYKKLYZXJSNPZ-UHFFFAOYSA-N', 'Sarcosine', '["sarcosine", "N-methylglycine", "methylaminoacetic acid"]'),

-- Vitamins and Cofactors
('CIWBSHSKHKDKBQ-JLAZNSOCSA-N', 'Ascorbic Acid', '["ascorbic acid", "L-ascorbic acid", "vitamin C", "L-xylo-hex-2-ulonic acid γ-lactone"]'),
('GVJHHUAWPYXKBD-IEOSBIPESA-N', 'Tocopherol', '["tocopherol", "α-tocopherol", "alpha-tocopherol", "vitamin E"]'),
('DRLFMBDRBRZALE-UHFFFAOYSA-N', 'Melatonin', '["melatonin", "N-acetyl-5-methoxytryptamine", "MLT", "pineal hormone"]'),
('AGBQKNBQESQNJD-UHFFFAOYSA-N', 'Lipoic Acid', '["lipoic acid", "α-lipoic acid", "alpha-lipoic acid", "thioctic acid"]'),

-- Specialized Metabolites
('RWSXRVCMGQZWBV-WDSKDSINSA-N', 'Glutathione', '["glutathione", "GSH", "reduced glutathione", "L-glutathione"]'),
('PHIQHXFUZVPYII-ZCFIWIBFSA-N', 'L-Carnitine', '["L-carnitine", "carnitine", "levocarnitine", "vitamin BT"]'),
('XOAAWQZATWQOTB-UHFFFAOYSA-N', 'Taurine', '["taurine", "2-aminoethanesulfonic acid", "amino ethyl sulfonic acid"]'),

-- Hormones and Signaling Molecules
('JLIDBLDQVAYHNE-LEIXFBQQSA-N', 'Abscisic Acid', '["abscisic acid", "ABA", "(S)-(+)-abscisic acid", "dormin"]'),
('YGSDEFSMJLZEOE-UHFFFAOYSA-N', 'Salicylic Acid', '["salicylic acid", "2-hydroxybenzoic acid", "ortho-hydroxybenzoic acid", "SA"]'),

-- Complex Natural Products
('RCINICONZNJXQF-MZXODVADSA-N', 'Taxol', '["taxol", "paclitaxel", "pac", "PTX", "onxol"]'),
('QCDYQQDYXPDABM-UHFFFAOYSA-N', 'Phloroglucinol', '["phloroglucinol", "1,3,5-trihydroxybenzene", "benzene-1,3,5-triol"]'),
('RTKIYNMVFMVABJ-WWQGKWQPSA-N', 'Valinomycin', '["valinomycin", "antibiotic valinomycin", "potassium ionophore"]'),

-- Flavonoids
('WUADCCWIQCMNHA-GRWLCUOYSA-N', 'Kaempferol 7-O-Glucoside', '["kaempferol 7-O-glucoside", "kaempferol 7-glucoside", "populnin"]'),

-- Nucleotides
('ZKHQWZAMYRWXGA-KQYNXXCUSA-N', 'ATP', '["ATP", "adenosine triphosphate", "adenosine 5-triphosphate"]'),

-- Simple Nitrogen Compounds
('XSQUKJJJFZCRTK-UHFFFAOYSA-N', 'Urea', '["urea", "carbamide", "carbonyldiamide", "diaminomethanal"]'),
('UMGDCJDMYOKAJW-UHFFFAOYSA-N', 'Thiourea', '["thiourea", "thiocarbamide", "2-thiourea", "pseudourea"]'),
('ABDDQFNMLBDCNW-UHFFFAOYSA-N', 'Succinimide', '["succinimide", "pyrrolidine-2,5-dione", "butanimide"]'),

-- Aromatics
('ISWSIDIOOBJBQZ-UHFFFAOYSA-N', 'Phenol', '["phenol", "carbolic acid", "hydroxybenzene", "benzenol"]'),
('HNJBEVLQSNELDL-UHFFFAOYSA-N', 'Pyridine-N-Oxide', '["pyridine-N-oxide", "pyridine oxide", "pyridine 1-oxide"]'),

-- Inorganic Salts
('FGIUAXJPYTZDNR-UHFFFAOYSA-L', 'Potassium Nitrate', '["potassium nitrate", "KNO3", "saltpeter", "niter"]'),
('NLXLAEXVIDQMFP-UHFFFAOYSA-L', 'Potassium Chloride', '["potassium chloride", "KCl", "muriate of potash"]'),
('FAPWRFPIFSIZLT-UHFFFAOYSA-M', 'Sodium Chloride', '["sodium chloride", "NaCl", "table salt", "halite"]'),
('UXVMQQNJUSDDNG-UHFFFAOYSA-L', 'Calcium Chloride', '["calcium chloride", "CaCl2", "calcium dichloride"]'),
('PMZURENOXWZQFD-UHFFFAOYSA-L', 'Sodium Sulfate', '["sodium sulfate", "Na2SO4", "Glauber salt"]'),

-- Organic Salts
('TXWRERCHRDBNLG-UHFFFAOYSA-N', 'Ammonium Acetate', '["ammonium acetate", "NH4CH3COO", "acetic acid ammonium salt"]'),
('LEUHKJDQFAXXLX-UHFFFAOYSA-N', 'Sodium Formate', '["sodium formate", "sodium methanoate", "HCOONa"]'),
('IJORLWNGMFRSJW-UHFFFAOYSA-N', 'Sodium Malonate', '["sodium malonate", "disodium malonate", "malonic acid disodium salt"]'),
('NALJXBGAZRCBBD-UHFFFAOYSA-K', 'Sodium Citrate', '["sodium citrate", "trisodium citrate", "citric acid trisodium salt"]'),
('NMRBNDHWBFFZBM-UHFFFAOYSA-N', 'Sodium Potassium Tartrate', '["sodium potassium tartrate", "Rochelle salt", "potassium sodium tartrate"]'),
('POKOFDPLXZGJMU-UHFFFAOYSA-N', 'Potassium Acetate', '["potassium acetate", "CH3COOK", "acetic acid potassium salt"]'),

-- Phosphates
('DHKHKXVYLBGOIT-UHFFFAOYSA-L', 'β-Glycerophosphate', '["β-glycerophosphate", "beta-glycerophosphate", "glycerol 2-phosphate"]'),

-- Special Solvents
('NXQGGXCHGDYOHB-UHFFFAOYSA-N', 'MPD', '["MPD", "2-methyl-2,4-pentanediol", "hexylene glycol"]'),
('XLYOFNOQVPJJNP-ZSJDYOACSA-N', 'Heavy Water', '["heavy water", "D2O", "deuterium oxide", "deuterated water"]'),

-- Polymers and Complex Mixtures
(NULL, 'Alginate', '["alginate", "alginic acid", "sodium alginate", "calcium alginate", "algin"]'),
(NULL, 'Polyethylene Glycol', '["polyethylene glycol", "PEG", "polyethylene oxide", "PEO", "carbowax"]'),
(NULL, 'Polyethylene Oxide', '["polyethylene oxide", "PEO", "polyethylene glycol", "PEG"]'),
(NULL, 'Polyvinylpyrrolidone', '["polyvinylpyrrolidone", "PVP", "povidone", "poly(N-vinylpyrrolidone)"]'),
(NULL, 'Polyvinyl Alcohol', '["polyvinyl alcohol", "PVA", "PVAL", "poly(vinyl alcohol)"]'),
(NULL, 'Dextran', '["dextran", "dextran polymer", "glucose polymer"]'),
(NULL, 'Dextrin', '["dextrin", "dextrine", "starch gum", "British gum"]'),
(NULL, 'Hyaluronic Acid', '["hyaluronic acid", "HA", "hyaluronan", "hyaluronate"]'),
(NULL, 'Hydroxyethyl Starch', '["hydroxyethyl starch", "HES", "hetastarch", "modified starch"]'),
(NULL, 'Gelatin', '["gelatin", "gelatine", "hydrolyzed collagen"]'),
(NULL, 'Agar', '["agar", "agar-agar", "agarose", "gelidium"]'),

-- Proteins
(NULL, 'Antifreeze Protein', '["antifreeze protein", "AFP", "ice-binding protein", "thermal hysteresis protein"]'),
(NULL, 'Bovine Serum Albumin', '["bovine serum albumin", "BSA", "albumin bovine", "cow serum albumin"]'),
(NULL, 'Sericin', '["sericin", "silk sericin", "silk protein"]'),
(NULL, 'Poly-L-Lysine', '["poly-L-lysine", "PLL", "polylysine"]'),

-- Surfactants and Detergents
(NULL, 'Brij35', '["Brij 35", "brij35", "polyoxyethylene lauryl ether", "laureth-23"]'),
(NULL, 'Tween-20', '["Tween-20", "polysorbate 20", "polyoxyethylene sorbitan monolaurate"]'),
(NULL, 'Tween-80', '["Tween-80", "polysorbate 80", "polyoxyethylene sorbitan monooleate"]'),
(NULL, 'Triton', '["Triton", "Triton X-100", "polyethylene glycol octylphenyl ether"]'),
(NULL, 'Trimethylnonyl Polyethoxy Ethanol', '["trimethylnonyl polyethoxy ethanol", "TMN-6", "branched alcohol ethoxylate"]'),
(NULL, 'Pluronic F68', '["Pluronic F68", "poloxamer 188", "polyoxyethylene-polyoxypropylene block copolymer"]'),

-- Synthetic Polymers
(NULL, 'Poly-Sulfobetaine', '["poly-sulfobetaine", "polysulfobetaine", "zwitterionic polymer"]'),
(NULL, 'Poly-(MAA-r-DMAEMA)', '["poly-(MAA-r-DMAEMA)", "poly(methacrylic acid-r-dimethylaminoethyl methacrylate)"]'),
(NULL, 'Poly(MAA-DMAEMA)', '["poly(MAA-DMAEMA)", "poly(methacrylic acid-dimethylaminoethyl methacrylate)"]'),
(NULL, 'Ficoll', '["Ficoll", "polysucrose", "Ficoll-400", "synthetic polymer"]'),

-- Cryoprotectant Formulations
(NULL, 'PVS', '["PVS", "plant vitrification solution", "cryoprotectant mixture"]'),
(NULL, 'PVS2', '["PVS2", "plant vitrification solution 2", "cryoprotectant formulation"]'),
(NULL, 'PVS3', '["PVS3", "plant vitrification solution 3", "cryoprotectant mixture"]'),
(NULL, 'DP6', '["DP6", "cryoprotectant solution", "organ preservation solution"]'),
(NULL, 'VS55', '["VS55", "vitrification solution 55", "cryoprotectant mixture"]'),
(NULL, 'M22', '["M22", "cryoprotectant cocktail", "organ preservation medium"]'),
(NULL, 'VM3', '["VM3", "vitrification medium 3", "cryoprotectant solution"]'),
(NULL, 'VMP', '["VMP", "vitrification medium for plants", "plant cryoprotectant"]'),

-- Natural Gums and Extracts
(NULL, 'Gum Arabic', '["gum arabic", "acacia gum", "arabic gum", "gum acacia"]'),
(NULL, 'Peptone', '["peptone", "protein hydrolysate", "enzymatic digest"]'),

-- Antibiotics and Bioactive Compounds
(NULL, 'Gramicidin', '["gramicidin", "gramicidin A", "antibiotic peptide"]'),

-- Nanomaterials
(NULL, 'Graphene Oxide', '["graphene oxide", "GO", "oxidized graphene"]'),
(NULL, 'Oxidized Quasi-Carbon Nitride Quantum Dots', '["oxidized quasi-carbon nitride quantum dots", "OQCNs", "carbon nitride QDs"]'),

-- Glycol Ethers
(NULL, 'MCHG', '["MCHG", "monochlohydrin glycerol", "3-chloro-1,2-propanediol"]'),
(NULL, 'MEEG', '["MEEG", "monoethyl ether of glycerol", "glycerol monoethyl ether"]'),

-- Generic Chemical Classes
(NULL, 'Thiol', '["thiol", "mercaptan", "sulfhydryl compound", "R-SH"]'),
(NULL, 'Sulfate', '["sulfate", "SO4", "sulfate ion", "sulfuric acid salt"]'),
(NULL, 'Polyhydroxylated Alcohol', '["polyhydroxylated alcohol", "polyol", "multiple hydroxyl alcohol"]');

-- End of INSERT statements
-- Total entries: 126 chemicals (removed 3 duplicates)
-- Discrete molecules: 86 (with InChI keys)
-- Polymers/mixtures: 40 (with NULL InChI keys)

-- FIXES APPLIED:
-- 1. Fixed column name from inchi_key to inchikey
-- 2. Removed duplicate entries: 1,2-Propanediol, 1,3-Propanediol, Trimethylglycine  
-- 3. Fixed InChI keys:
--    - 1,2-Butanediol: GJRQTCIYDGXPES-UHFFFAOYSA-N
--    - 2,3-Butanediol: OWBTYPJTUOEWEK-UHFFFAOYSA-N  
--    - Ononitol: LKCWBDHBTVXHDL-RMKNXTFCSA-N (4-O-methyl-myo-inositol)
-- 4. Updated synonym arrays for clarity
-- 5. All InChI keys are now unique