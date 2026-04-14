Chapter is used to describe a more in depth interpretation of how foundational models are trained + differential of datasets determine how models themselves perform. 
	We currently use "transformer architecture"

	Models go through both Pre and Post Training

Pretraining focuses on usability meanwhile post training is created to match human users intent.

Models are trained on "sampling" where the are forced to make selection from dozens of options. 

Models can only be good at specific tasks if it was included in their training data (img classification or translation)

AI training data mostly consists of web scrapings being done from the web, therefore its quality isn't necessarily the best. CRUITAL TO CREATE DATASETS THAT ALIGN WITH YOUR NEEDS not foundational models.

Since English was the majority language amongst its training data, it significantly shows in examples of mathematics and highest success rates when prompted in english.

	Without specific examples within its training data, there is only so much a "GPT" is able to assist with domain specific topics. Note to self, the more its exposed examples in its dataset, the better the gpt will learn to make the correct selections in its answering ability.

Launching Architecture such as 7B vs 175B will vary(the larger the value the more difficult it is to launch)

Transformer Architecture evolved from Sequence based ML. Tradionally (seq2seq) follows a flow style a such a -> b-> c then outputs into one final results whereas transformer model each input maps to an independant part of the output. a-> b->c

	Transform model allows for different values to be established on each input for example when trying to determine which values of a prompt mean more to the output. 

Three key components to decoding an input through a tranformer model
	 the query vector.(person looking for information to complete the task) Also represents the decoder at each step (what is currently happening)

The key vector which from the book example pertains to the page number(can be found here). Think index reference to a dictionary 

Lastly the value vector which refers to a pages content(think of a definition on page 17)

High score refers to more vector value being utilized in the action.(think complete definition with adjectives)

Attention functions operability- each of the functions vector, key and query are calculated when combining inputs with the each of the function. 

Models have hidden dimentions(an unrevleaved size) these attention function have multiple heads to split functions between so in ex models had 32 heads in order to access prev tokens by distributing each of the querys between its 32 heads. so 4096 model gets divided by 32.

results of those functions are then connected and fed into and output matrix which reformats the context of its finding before moving on to next steps.

concatenated- to connect or assemble together

	Note to self, as the transformer architecture has been around for some time, newer architectures scuh as Jamba Mamba appear offering transformer like qualities whith longer context windows. New architectures dont require such large datacenters as it can be ran off one card vs needing entire systems.(at home scalability)

Parameter metrics on models- the larger the parameter(7b vs 13b) the more openness it has to learning and output strength. though only when dealing with identical model generations, as new models release, they outperform old ones even w smaller parameters.

GPU requirements are measured as such model paramerter(7b for ex) multiplied by 2 bytes per parameter would require a 14gb card.

Larger models sparcing(meaning it only uses about 10% of model for computing blocks  might have more "breathing room", meaning more computing and data store with more sparcity with less effort.

MoE(models of experts)- foundational models with expert blocks in its architecture, each of which only gets used depending on the tasks.(each block is only used when needed rest is kept for sparcity)

training data is tradionoanlly 1 trillions tokens and after passthroguh it doubles into 2 trillion tokens.

quanitiy, quality, and diversity of data is the cruital factors of data

calculations and budgeting when it comes to training LLMs is output in "chinchilla rule of training llms"- often 20x token of model size (3b models needs 60b tokens)

interesting to note how model quality isnt every, since llama isnt necessarily amazing, but its smaller, and its parameters are easier to adjust over time making it more flexibile, and cheaper interference cost.

	Supervised fine tuning helps ajust models away from just completion of responses but adjust reponses closer to human intent.

	Post traning responses can be judged from a scale of right and rong and be assignged a value which later is embedded into training.

	In order to refine model outputs, examples of proper responses may be outputted as "demonstration data". The more examples provided the closer to user intent you get.

	It is important to have range and effective lableing in your demonstration data.

	finetuning ontop of an already strong model is the most ideal ourput for example logging winning and losing responses using (what gpt used was instructgpt)

	Test time compute- generate multiple outputs to increase the likelhood of a proper response. The larger the varierty of responses the more options you haev of finetuninig your agent.(utilize our /selfimprove to query conversation logs and fietune repsones when mutliple outputs are provided. This can be done via probablilty)

	Another option to validatate test time computer would be a verifyer to outputs. Trained verifiers have the capacity to increase perforamnce by 30x with smaller sized models.(hence why we had established our /selfimprove)

	To further expand upon the point of varietal ouputs, training data suggest that up until a certain point does large scale ouputs negaltivly impact the result choices by the llm

	When expecting "exact answers" picking out the most common answers from a set of queires can help refine the model a gemini did when training it for the medical boards. (32 ouputs per question exp multiple choice had led them to ideal training and sucess).
	if a models responses dont change over varieiety of outputs its conidered robust.(if not then continue refining)
		ideally when perfomring TDD on realtime APi testing, the continuous testing until proper output is met has proven to be the most sucessful integral part in improving
		

Semantic parsting to keep structured outputs in a certain format.
(for example how labaide outputs options for phlebotamists in test name, code, and panel components)

	As we had disociverd in the past, with too long of a max token length, performance had drastically dreduced making the response too slow and unusable.

	Prompt validation techniques- Upon prompting the large language model, it appears optimal to incorperate a validation clause ensuring certaining in its reponse with a certain output. Two inputs are inscribed into the prompt one of the request second to validat the first.

	Constrainetd sampling inside the actaul LLM prevenets certain logits from slipping throguh the cracked helping ensure accuracy in the model.

	In finetuning- models outputs ar canable of being guaranteed when the architecutre is formateed to support it.
	