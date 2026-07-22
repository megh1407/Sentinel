"""
============================================================
Sentinel Data Engine

Worker Generator 2.0

Realistic worker behaviour simulation.
============================================================
"""

import random
from uuid import uuid4

from config.constants import WORKER_ROLES, ZONES
from events.worker_event import WorkerEvent


class WorkerGenerator:

    CERTIFICATIONS = [

        "Hot Work",
        "Electrical",
        "Confined Space",
        "First Aid",
        "Chemical Handling",
        "LOTO"

    ]

    def __init__(self, total_workers=50):

        self.workers = []

        self.initialize(total_workers)

    # =====================================================

    def initialize(self, total):

        for _ in range(total):

            self.workers.append({

                "worker_id": str(uuid4()),

                "role": random.choice(WORKER_ROLES),

                "contractor": random.choice([True, False]),

                "zone": random.choice(ZONES),

                "fatigue": random.uniform(0.0,0.15),

                "heart_rate": random.randint(68,82),

                "body_temp": random.uniform(36.3,36.9),

                "ppe":{

                    "helmet":True,
                    "vest":True,
                    "gloves":True,
                    "boots":True,
                    "mask":True,
                    "harness":False,
                    "goggles":True,
                    "ear_protection":True

                },

                "certifications":random.sample(

                    self.CERTIFICATIONS,

                    random.randint(2,5)

                )

            })

    # =====================================================

    def update(self,timeline):

        hour=timeline.hour

        for worker in self.workers:

            # Random movement

            if random.random()<0.08:

                worker["zone"]=random.choice(ZONES)

            # Fatigue increases during shift

            worker["fatigue"]=min(

                1.0,

                worker["fatigue"]+

                random.uniform(0.001,0.01)

            )

            # Heart rate

            worker["heart_rate"]=int(

                70+

                worker["fatigue"]*35+

                random.randint(-4,4)

            )

            # Body temperature

            worker["body_temp"]=round(

                36.5+

                worker["fatigue"]*0.6+

                random.uniform(-0.2,0.2),

                1

            )

            # PPE violations

            if random.random()<0.015:

                item=random.choice(

                    list(worker["ppe"].keys())

                )

                worker["ppe"][item]=False

            # Night shift fatigue

            if hour>=22 or hour<6:

                worker["fatigue"]=min(

                    1.0,

                    worker["fatigue"]+0.02

                )

    # =====================================================

    def generate_events(self,site_id):

        events=[]

        for worker in self.workers:

            event=WorkerEvent(

                site_id=site_id,

                zone_id=worker["zone"]

            )

            location={

                "x":round(random.uniform(0,100),2),

                "y":round(random.uniform(0,100),2),

                "floor":0,

                "accuracy_m":round(random.uniform(0.5,2),2)

            }

            biometrics={

                "heart_rate":worker["heart_rate"],

                "body_temp":worker["body_temp"],

                "fatigue_index":round(worker["fatigue"],2),

                "spo2":round(random.uniform(96,100),1)

            }

            event.set_worker_data(

                event_type="worker.location",

                worker_id=worker["worker_id"],

                role=worker["role"],

                contractor=worker["contractor"],

                location=location,

                ppe_status=worker["ppe"],

                biometrics=biometrics,

                certifications=worker["certifications"]

            )

            events.append(event)

        return events

    # =====================================================

    def get_workers(self):

        return self.workers