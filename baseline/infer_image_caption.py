import argparse
import os
from tqdm import tqdm
import json
from PIL import Image
import torch
from accelerate import Accelerator


def blip_base(model_path, dataset_path, prompt):
    os.environ["CUDA_VISIBLE_DEVICES"] = "1"
    from transformers import BlipProcessor, BlipForConditionalGeneration
    # 加载模型
    processor = BlipProcessor.from_pretrained(model_path)
    model = BlipForConditionalGeneration.from_pretrained(model_path).to("cuda")
    # 推理图像
    result = {}
    for image in tqdm(dataset_path):
        raw_image = Image.open(image).convert('RGB')
        inputs = processor(raw_image, "a photography of" , return_tensors="pt").to("cuda")
        out = model.generate(**inputs)
        image_id = os.path.splitext(image)[0].split('/')[-1]
        result[image_id] = processor.decode(out[0], skip_special_tokens=True)
    # 保存结果
    with open('../results/image_caption/'+model_path.split('/')[-1]+'.json', 'w') as file:
        json.dump(result, file, indent=4)


def blip2(model_path, dataset_path, prompt):
    os.environ["CUDA_VISIBLE_DEVICES"] = "1"
    from transformers import Blip2Processor, Blip2ForConditionalGeneration
    # 加载模型
    processor = Blip2Processor.from_pretrained(model_path)
    model = Blip2ForConditionalGeneration.from_pretrained(model_path, device_map="auto")
    # 推理图像
    result = {}
    for image in tqdm(dataset_path):
        raw_image = Image.open(image).convert('RGB')
        inputs = processor(raw_image, prompt, return_tensors="pt").to("cuda")
        out = model.generate(**inputs)
        image_id = os.path.splitext(image)[0].split('/')[-1]
        result[image_id] = processor.decode(out[0], skip_special_tokens=True)
    # 保存结果
    with open('../results/image_caption/'+model_path.split('/')[-1]+'.json', 'w') as file:
        json.dump(result, file, indent=4)


def instructblip(model_path, dataset_path, prompt):
    os.environ["CUDA_VISIBLE_DEVICES"] = "1"
    from transformers import InstructBlipProcessor, InstructBlipForConditionalGeneration
    # 加载模型
    model = InstructBlipForConditionalGeneration.from_pretrained(model_path).to("cuda")
    processor = InstructBlipProcessor.from_pretrained(model_path)
    # 推理图像
    result = {}
    for image in tqdm(dataset_path):
        raw_image = Image.open(image).convert('RGB')
        inputs = processor(images=raw_image, text=prompt, return_tensors="pt").to("cuda")
        outputs = model.generate(
                **inputs,
                do_sample=False,
                num_beams=5,
                max_length=256,
                min_length=1,
                top_p=0.9,
                repetition_penalty=1.5,
                length_penalty=1.0,
                temperature=1,
        )
        image_id = os.path.splitext(image)[0].split('/')[-1]
        result[image_id] = processor.batch_decode(outputs, skip_special_tokens=True)[0].strip()
    # 保存结果
    with open('../results/image_caption/'+model_path.split('/')[-1]+'.json', 'w') as file:
        json.dump(result, file, indent=4)


def mplug_owl(model_path, dataset_path, prompt):
    os.environ["CUDA_VISIBLE_DEVICES"] = "1"
    from mPLUG_Owl.mplug_owl.modeling_mplug_owl import MplugOwlForConditionalGeneration
    from mPLUG_Owl.mplug_owl.processing_mplug_owl import MplugOwlImageProcessor, MplugOwlProcessor
    from transformers import AutoTokenizer
    # 加载模型
    pretrained_ckpt = model_path
    model = MplugOwlForConditionalGeneration.from_pretrained(
        pretrained_ckpt,
        torch_dtype=torch.bfloat16,
    )
    image_processor = MplugOwlImageProcessor.from_pretrained(pretrained_ckpt)
    tokenizer = AutoTokenizer.from_pretrained(pretrained_ckpt)
    processor = MplugOwlProcessor(image_processor, tokenizer)
    # 推理图像
    prompts = [
        "The following is a conversation between a curious human and AI assistant. The assistant gives helpful, detailed, and polite answers to the user's questions."
        +"\nHuman: <image>"
        +"\nHuman: "
        +prompt 
        +"\nAI: "
    ]
    generate_kwargs = {
        'do_sample': True,
        'top_k': 5,
        'max_length': 512
    }
    result = {}
    model.to("cuda")
    for image in tqdm(dataset_path):
        image = [image]
        images = [Image.open(_) for _ in image]
        inputs = processor(text=prompts, images=images, return_tensors='pt')
        inputs = {k: v.bfloat16() if v.dtype == torch.float else v for k, v in inputs.items()}
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        with torch.no_grad():
            res = model.generate(**inputs, **generate_kwargs)
        image_id = os.path.splitext(image[0])[0].split('/')[-1]
        result[image_id] = tokenizer.decode(res.tolist()[0], skip_special_tokens=True)
    # 保存结果
    with open('../results/image_caption/'+model_path.split('/')[-1]+'.json', 'w') as file:
        json.dump(result, file, indent=4)


def mplug_owl2(model_path, dataset_path, prompt):
    os.environ["CUDA_VISIBLE_DEVICES"] = "1"
    from transformers import TextStreamer
    from mPLUG_Owl2.mplug_owl2.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN
    from mPLUG_Owl2.mplug_owl2.conversation import conv_templates, SeparatorStyle
    from mPLUG_Owl2.mplug_owl2.model.builder import load_pretrained_model
    from mPLUG_Owl2.mplug_owl2.mm_utils import process_images, tokenizer_image_token, get_model_name_from_path, KeywordsStoppingCriteria
    def call(image_file, prompt):
        model_name = get_model_name_from_path(model_path)
        tokenizer, model, image_processor, context_len = load_pretrained_model(model_path, None, model_name, load_8bit=False, load_4bit=False, device="cuda")

        conv = conv_templates["mplug_owl2"].copy()
        roles = conv.roles

        image = Image.open(image_file).convert('RGB')
        max_edge = max(image.size) # We recommand you to resize to squared image for BEST performance.
        image = image.resize((max_edge, max_edge))

        image_tensor = process_images([image], image_processor)
        image_tensor = image_tensor.to(model.device, dtype=torch.float16)

        inp = DEFAULT_IMAGE_TOKEN + prompt
        conv.append_message(conv.roles[0], inp)
        conv.append_message(conv.roles[1], None)
        prompt = conv.get_prompt()

        input_ids = tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors='pt').unsqueeze(0).to("cuda")
        stop_str = conv.sep2
        keywords = [stop_str]
        stopping_criteria = KeywordsStoppingCriteria(keywords, tokenizer, input_ids)
        streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

        temperature = 0.7
        max_new_tokens = 512

        with torch.inference_mode():
            output_ids = model.generate(
                input_ids,
                images=image_tensor,
                do_sample=True,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
                streamer=streamer,
                use_cache=True,
                stopping_criteria=[stopping_criteria])

        outputs = tokenizer.decode(output_ids[0, input_ids.shape[1]:]).strip()
        return outputs
    
    # 推理图像
    result = {}
    for image in tqdm(dataset_path):
        output = call(image, prompt)
        image_id = os.path.splitext(image)[0].split('/')[-1]
        result[image_id] = output
    # 保存结果
    with open('../results/image_caption/'+model_path.split('/')[-1]+'.json', 'w') as file:
        json.dump(result, file, indent=4)


def llava(model_path, dataset_path, prompt):
    from LLaVA.llava.model.builder import load_pretrained_model
    from LLaVA.llava.mm_utils import get_model_name_from_path
    from LLaVA.llava.eval.run_llava import eval_model
    # 加载模型
    tokenizer, model, image_processor, context_len = load_pretrained_model(
        model_path=model_path,
        model_base=None,
        model_name=get_model_name_from_path(model_path)
    )
    # 推理图像
    result = {}
    for image in tqdm(dataset_path):
        args = type(
            'Args', (), {
            "model_path": model_path,
            "model_base": None,
            "model_name": get_model_name_from_path(model_path),
            "query": prompt,
            "conv_mode": None,
            "image_file": image,
            "sep": ",",
            "temperature": 0,
            "top_p": None,
            "num_beams": 1,
            "max_new_tokens": 512
        })()
        output = eval_model(args)
        image_id = os.path.splitext(image)[0].split('/')[-1]
        result[image_id] = output
    # 保存结果
    with open('../results/image_caption/'+model_path.split('/')[-1]+'.json', 'w') as file:
        json.dump(result, file, indent=4)


def openflamingo(model_path, dataset_path, prompt):
    from Flamingo.open_flamingo import create_model_and_transforms
    # 加载模型
    model, image_processor, tokenizer = create_model_and_transforms(
        clip_vision_encoder_path="ViT-L-14",
        clip_vision_encoder_pretrained="openai",
        lang_encoder_path="../models/mpt-1b-redpajama-200b",
        tokenizer_path="../models/mpt-1b-redpajama-200b",
        cross_attn_every_n_layers=1
    )
    model.load_state_dict(torch.load(model_path + "/checkpoint.pt"), strict=False)
    model.to('cuda')
    tokenizer.padding_side = "left"
    result = {}
    for i in tqdm(dataset_path):
        current = i.split('/')[-1][2]
        background = i.split('/')[-2]
        # print(background)
        input_prompt = f"Output:A woman wearing a net on her head cutting a cake.<|endofchunk|><image>Output:"
        query_image = Image.open(i)
        lang_x = tokenizer(
            [input_prompt],
            return_tensors="pt",
        ).to('cuda')
        vision_x = [image_processor(query_image).unsqueeze(0).to('cuda')]

        vision_x = torch.cat(vision_x, dim=0)
        vision_x = vision_x.unsqueeze(1).unsqueeze(0)
        generated_text = model.generate(
            vision_x=vision_x,
            lang_x=lang_x["input_ids"],
            attention_mask=lang_x["attention_mask"],
            max_new_tokens=128,
            num_beams=3,
        )
        output = tokenizer.decode(generated_text[0])

        image_id = os.path.splitext(i)[0].split('/')[-1]
        # output = output.replace(prompt, "").replace("<|endofchunk|>","")
        output = output.split("Output:")[2].replace(input_prompt, "").replace("<|endofchunk|>","")
        result[image_id] = output
        print(image_id, output)

    # 保存结果
    with open('../results/image_caption/'+model_path.split('/')[-1]+'.json', 'w') as file:
        json.dump(result, file, indent=4)


def mmicl(model_path, dataset_path, prompt):
    from MIC.model.instructblip import InstructBlipConfig, InstructBlipModel, InstructBlipPreTrainedModel,InstructBlipForConditionalGeneration,InstructBlipProcessor
    import transformers
    # 加载模型
    processor_ckpt = "../models/instructblip-flan-t5-xl"
    config = InstructBlipConfig.from_pretrained(model_path)
    model = InstructBlipForConditionalGeneration.from_pretrained(
        model_path,
        config=config).to('cuda:0',dtype=torch.bfloat16) 

    image_palceholder="图"
    sp = [image_palceholder]+[f"<image{i}>" for i in range(20)]
    processor = InstructBlipProcessor.from_pretrained(
        processor_ckpt
    )
    sp = sp+processor.tokenizer.additional_special_tokens[len(sp):]
    processor.tokenizer.add_special_tokens({'additional_special_tokens':sp})
    if model.qformer.embeddings.word_embeddings.weight.shape[0] != len(processor.qformer_tokenizer):
        model.qformer.resize_token_embeddings(len(processor.qformer_tokenizer))
    replace_token="".join(32*[image_palceholder])

    result = {}
    for i in tqdm(dataset_path):

        query_image = Image.open(i)
        images = [query_image]

        input_prompt = [f'image 0 is <query_image>{replace_token}.Question: <query_image>{prompt} Answer:'
        ]
        input_prompt = " ".join(input_prompt)

        inputs = processor(images=images, text=input_prompt, return_tensors="pt")

        inputs['pixel_values'] = inputs['pixel_values'].to(torch.bfloat16)
        inputs['img_mask'] = torch.tensor([[1 for i in range(len(images))]])
        inputs['pixel_values'] = inputs['pixel_values'].unsqueeze(0)

        inputs = inputs.to('cuda:0')
        outputs = model.generate(
                pixel_values = inputs['pixel_values'],
                input_ids = inputs['input_ids'],
                attention_mask = inputs['attention_mask'],
                img_mask = inputs['img_mask'],
                do_sample=False,
                max_length=512,
                min_length=20,
                num_beams=8,
                set_min_padding_size =False,
        )
        output = processor.batch_decode(outputs, skip_special_tokens=True)[0].strip()
        image_id = os.path.splitext(i)[0].split('/')[-1]
        result[image_id] = output
        print(image_id, output)
    
    with open('../results/image_caption/'+model_path.split('/')[-1]+'.json', 'w') as file:
        json.dump(result, file, indent=4)

def gpt_4v(api_key, dataset_path, prompt):
    from openai import OpenAI
    import httpx
    import base64
    def encode_image_to_base64(image_path): 
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    client = OpenAI(
        base_url="https://oneapi.xty.app/v1", 
        api_key=api_key,
        http_client=httpx.Client(
            base_url="https://oneapi.xty.app/v1",
            follow_redirects=True,
        ),
    )

        # 推理
    result = {}

    for i in tqdm(dataset_path):
        image_two = encode_image_to_base64(i)
        image_two_format = i.split('/')[-1].split('.')[-1]
        try: 
            response = client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_two_format};base64,{image_two}",
                            },
                        },
                    ],
                    }
                ],
                max_tokens=512,
            )
            output = response.choices[0].message.content
            image_id = os.path.splitext(i)[0].split('/')[-1]
            result[image_id] = output
            print(image_id, output)
        except:
            pass
    with open('../results/image_caption/'+api_key.split('/')[-1]+'.json', 'w') as file:
        json.dump(result, file, indent=4)


    

# 加载图像数据集
def load_dataset(dataset_path):
    images = []
    for root, dirs, files in os.walk(dataset_path):
        for file in files:
            if file.endswith(('.png', '.webp')):
                images.append(os.path.join(root, file))
    return images

# 模型文件路径
PATH = {
    'BLIP-Base': '../models/blip-image-captioning-base',
    'BLIP2-XL': '../models/blip2-flan-t5-xl',
    'BLIP2-XXL': '../models/blip2-flan-t5-xxl',
    'InstructBLIP-XL': '../models/instructblip-flan-t5-xl',
    'InstructBLIP-XXL': '../models/instructblip-flan-t5-xxl',
    'mPLUG-owl-7B': '../models/mplug-owl-llama-7b',
    'mPLUG-owl2-7B': '../models/mplug-owl2-llama2-7b',
    'LLaVA-1.5-7B': '../models/llava-v1.5-7b',
    'LLaVA-1.6-7B': '../models/llava-v1.6-vicuna-7b',
    'OpenFlamingo': '../models/OpenFlamingo-3B-vitl-mpt1b',
    'MMICL': '../models/MMICL-Instructblip-T5-xl',
    'Otter': "../models/OTTER-Image-LLaMA7B-LA-InContext",
    'GPT-4V': 'sk-hkR7ohdkEqFjD9MiEc22B0C392484eE692Ca0aD3F8B06c5c'
}

# 模型调用函数
FUNCTION = {
    'BLIP-Base': blip_base,
    'BLIP2-XL': blip2,
    'BLIP2-XXL': blip2,
    'InstructBLIP-XL': instructblip,
    'InstructBLIP-XXL': instructblip,
    'mPLUG-owl-7B': mplug_owl,
    'mPLUG-owl2-7B': mplug_owl2,
    'LLaVA-1.5-7B': llava,
    'LLaVA-1.6-7B': llava,
    'OpenFlamingo': openflamingo,
    'MMICL': mmicl,
    'GPT-4V': gpt_4v
}

 
if __name__ == '__main__':
    # 获取控制台参数
    parser = argparse.ArgumentParser()
    parser.add_argument("-model", type=str, required=True, choices=list(PATH.keys()))
    args = parser.parse_args()
    # 模型路径
    model = PATH[args.model]
    # 提示词
    prompt = "Describe this image."
    # 图像数据集
    images = load_dataset("../dataset")
    # 模型推理
    FUNCTION[args.model](model, dataset_path=images, prompt=prompt)