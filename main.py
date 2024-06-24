from TikTokApi import TikTokApi
import asyncio
from TikTokApi.exceptions import EmptyResponseException
import logging
import cv2
import requests
from moviepy.editor import VideoFileClip, AudioFileClip
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import time
from reportlab.lib.pagesizes import letter

ms_token = ("BiTnb3OcCaojVo-zNbuZXtxj3ZLT"
            "-bw3FYtVNLDvmsKtVS1ELnmbZAPWKbyZSvYboqBiG0T6dcq2obq77R7saQN2iREwCLTDVyurEl6rNdgjEI6DG"
            ""
            "--SqF9RcdForttwMnYuSgA2pGLipg==")

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TikTokAPIHandler:
    max_count_per_request = 30  # tiktok has limit per 1 request

    def __init__(self, save_path=r"E:/projects/projects/fetchingTiktok/videous", count=100, cookie=ms_token,
                 region="BY"):
        self.save_path = save_path
        self.region = region
        self.ms_token = ms_token
        self.count = count
        self.num_request = (self.count + self.max_count_per_request - 1) // self.max_count_per_request

    async def fetch_trending_videos(self, api):
        all_videos = []

        for _ in range(self.num_request):
            try:
                async for video in api.trending.videos(
                        count=min(self.max_count_per_request, self.count - len(all_videos)),
                        region=self.region):
                    all_videos.append(video)
                    if len(all_videos) >= self.count:
                        break
                await asyncio.sleep(1)  # delay between requests to avoid rate limits

            except EmptyResponseException as e:
                logger.error(f"Empty response from TikTok: {e}")
                break
            except Exception as e:
                logger.error(f"An error occurred: {e}")
                break

        return all_videos

    @staticmethod
    def get_tiktok_video_nowatermark(url):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/91.0.4472.124 Safari/537.36"
            }
            api_url = f"https://snaptik.app/abc?url={url}"
            response = requests.get(api_url, headers=headers)
            if response.status_code != 200:
                logger.error(f"Failed to get no watermark URL for {url}: HTTP {response.status_code}")
                return None

            video_data = response.json()
            if 'data' not in video_data or 'video_no_watermark' not in video_data['data']:
                logger.error(f"Unexpected video data structure for {url}")
                return None

            nowatermark_url = video_data['data']['video_no_watermark']
            return nowatermark_url

        except Exception as e:
            logger.error(f"Failed to get no watermark URL for {url}: {e}")
            return None

    @staticmethod
    def change_video_speed(input_path, output_path, speed_factor=0.9):
        cap = cv2.VideoCapture(input_path)

        if not cap.isOpened():
            logger.error(f"Could not open the video file {input_path}")
            return

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        fps = cap.get(cv2.CAP_PROP_FPS) * speed_factor
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            out.write(frame)

        cap.release()
        out.release()

    @staticmethod
    def change_video_resolution(input_path, output_path, scale_percent=90):
        cap = cv2.VideoCapture(input_path)

        if not cap.isOpened():
            logger.error(f"Could not open the video file {input_path}")
            return

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        new_width = int(width * scale_percent / 100)
        new_height = int(height * scale_percent / 100)

        out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), cap.get(cv2.CAP_PROP_FPS),
                              (new_width, new_height))

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
            out.write(frame)

        cap.release()
        out.release()

    @staticmethod
    def replace_audio(video_path, audio_path, output_path):
        video_clip = VideoFileClip(video_path)
        audio_clip = AudioFileClip(audio_path)

        # Ensure audio matches video duration
        if audio_clip.duration > video_clip.duration:
            audio_clip = audio_clip.subclip(0, video_clip.duration)

        # Set new audio
        video_clip = video_clip.set_audio(audio_clip)

        # Write video with new audio
        video_clip.write_videofile(output_path, codec='libx264', audio_codec='aac', temp_audiofile='temp_audio.mp3',
                                   remove_temp=True)

    async def download_videos_without_watermark(self, api, videos):
        for tiktok in videos:
            try:
                video_id = tiktok.id
                author_id = tiktok.author.user_id
                video_url = f'https://www.tiktok.com/@{author_id}/video/{video_id}'

                logger.info(f"Downloading video {video_id} from {video_url} without watermark")

                url_without_watermark = self.get_tiktok_video_nowatermark(video_url)
                if not url_without_watermark:
                    logger.error(f"Skipping video {video_id}: Could not get no watermark URL")
                    continue

                data = requests.get(url_without_watermark).content

                save_file_path = f"{self.save_path}/{video_id}.mp4"
                output_path = f"{self.save_path}/slow_speed/{video_id}.mp4"

                with open(save_file_path, 'wb') as output:
                    output.write(data)

                self.change_video_speed(save_file_path, output_path, 0.9)
                self.change_video_resolution(save_file_path, output_path, 90)
                self.replace_audio(save_file_path, "song.mp3", output_path)

                logger.info(f"Video {video_id} downloaded successfully without watermark")

            except Exception as e:
                logger.error(f"Error downloading video {video_id}: {e}")

    async def trending_videos(self):
        try:
            async with TikTokApi() as api:
                await api.create_sessions(ms_tokens=[self.ms_token], num_sessions=1, sleep_after=3, headless=False)

                logger.debug("Fetching trending videos")
                videos = await self.fetch_trending_videos(api)

                for video in videos:
                    print(video.as_dict)

                logger.debug("Downloading videos without watermark")
                await self.download_videos_without_watermark(api, videos)

        except Exception as e:
            logger.error(f"An error occurred: {e}")


class Report:
    def __init__(self, filename):
        self.filename = filename
        self.width, self.height = letter

    def create_new_page(self):
        c = canvas.Canvas(self.filename, pagesize=letter)
        return c

    def write(self, c, text):
        c = canvas.Canvas(self.filename, pagesize=letter)

        lines = text.splitlines()

        x, y = 100, self.height - 100

        for line in lines:
            c.drawString(x, y, line)
            y -= 15

        c.save()


if __name__ == '__main__':

    start = time.time()
    asyncio.run(TikTokAPIHandler().trending_videos())
    end = time.time()

    try:
        filename = "summarize.pdf"
        summarize = Report(filename)

        c = summarize.create_new_page()
        text = (
            f"Number of videos processed: 100;\n"
            f"Taken time for entire process: {end - start} sec;\n"
            f"I had an issue with downloading videos without watermarks. "
            f"This answer helped me:\n"
            f"https://stackoverflow.com/questions/63414894/how-to-get-tiktok-nowatermark-video-url-if-i-have-video-id"
        )

        summarize.write(c, text)
        logger.info("Report was successfully created!")

    except Exception as e:
        logger.error(f"Exception: {e}")

