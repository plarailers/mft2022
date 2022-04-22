from Components import *
from Communication import *


class State:
    STRAIGHT_UNIT = 21.5  # 直線レールの長さ[cm]
    CURVE_UNIT = 16.9  # 曲線レールの長さ[cm]

    # __init__で線路形状と車両の配置を定義する
    def __init__(self):
        self.communication = Communication()
        self.junctionList: list[Junction] = []
        self.sectionList: list[Section] = []
        self.sensorList: list[Sensor] = []
        self.stationList: list[Station] = []
        self.trainList: list[Train] = []

        # Junction(id, servoId)
        self.junctionList.append(Junction(0, -1))
        self.junctionList.append(Junction(1, -1))
        self.junctionList.append(Junction(2, 0))
        self.junctionList.append(Junction(3, -1))

        # Section(id, sourceJuncction, targetJuncction, sourceServoState, targetServoState, length)
        self.sectionList.append(Section(0, self.getJunctionById(3), self.getJunctionById(0), Junction.ServoState.NoServo, Junction.ServoState.NoServo, State.STRAIGHT_UNIT * 5.5))
        self.sectionList.append(Section(1, self.getJunctionById(0), self.getJunctionById(1), Junction.ServoState.NoServo, Junction.ServoState.NoServo, State.STRAIGHT_UNIT * 5 + State.CURVE_UNIT * 4))
        self.sectionList.append(Section(2, self.getJunctionById(1), self.getJunctionById(2), Junction.ServoState.Straight, Junction.ServoState.Straight, State.STRAIGHT_UNIT * 5.5))
        self.sectionList.append(Section(3, self.getJunctionById(1), self.getJunctionById(2), Junction.ServoState.Curve, Junction.ServoState.Curve, State.STRAIGHT_UNIT * 5.5))
        self.sectionList.append(Section(4, self.getJunctionById(2), self.getJunctionById(3), Junction.ServoState.NoServo, Junction.ServoState.NoServo, State.STRAIGHT_UNIT * 3 + State.CURVE_UNIT * 4))
        # 場合によっては、初回の着発番線に合わせてここにtoggleを挟む必要がある

        # Sensor(id, section, position)
        self.sensorList.append(Sensor(0, self.getSectionById(1), State.STRAIGHT_UNIT * 2.5 + State.CURVE_UNIT * 2))
        self.sensorList.append(Sensor(1, self.getSectionById(4), State.STRAIGHT_UNIT * 1.5 + State.CURVE_UNIT * 2))

        # Station(id, name)
        self.stationList.append(Station(0, "A"))  # A駅を追加
        self.stationList.append(Station(1, "B"))  # B駅を追加

        # section.putStation(station, stationPosition)
        self.getSectionById(0).putStation(self.getStationById(0), State.STRAIGHT_UNIT * 3)  # section0に駅0を追加
        self.getSectionById(2).putStation(self.getStationById(1), State.STRAIGHT_UNIT * 3)  # section2に駅1を追加
        self.getSectionById(3).putStation(self.getStationById(1), State.STRAIGHT_UNIT * 3)  # section3に駅1を追加

        # junction.belogStation
        self.getJunctionById(1).belongStation = self.getStationById(1)
        self.getJunctionById(2).belongStation = self.getSectionById(1)

        # Train(initialSection, initialPosition)
        self.trainList.append(Train(0, self.getSectionById(0), State.STRAIGHT_UNIT * 3))  # 列車0をsection0に配置
        self.trainList.append(Train(1, self.getSectionById(2), State.STRAIGHT_UNIT * 3))  # 列車1をsection2に配置

    # 現実世界の状態を取得しStateに反映する. 定期的に実行すること
    def update(self):
        # 情報取得
        self.communication.update()

        # 列車位置更新
        while self.communication.availableTrainSignal() > 0:
            trainSignal = self.communication.receiveTrainSignal()
            id = trainSignal.trainId
            delta = trainSignal.delta
            trainToMove = self.getTrainById(id)
            trainToMove.move(delta)

        # センサによる補正
        while self.communication.availableSensorSignal() > 0:
            id = self.communication.receiveSensorSignal()
            sensor = self.getSensorById(id)
            # sensorと同じセクションにいるtrainを取得して位置を補正
            train = self.getTrainInSection(sensor.belongSection)
            if train != None:
                train.move(sensor.position - train.mileage)

    # Stateに格納されている状態を現実世界に送信する. 各種計算後に実行すること
    def sendCommand(self):
        # 車両への指令送信
        for train in self.trainList:
            self.communication.sendInput(train.id, train.targetSpeed)

        # ポイントへの指令送信
        for junction in self.junctionList:
            if junction.servoId > -1:
                self.communication.sendToggle(junction.id, junction.outServoState)
                # inServoStateは、実際にはサーボモーターがついていないので送信しない

    def getJunctionById(self, id: int) -> Junction:
        return list(filter(lambda item: item.id == id, self.junctionList))[0]

    def getSectionById(self, id: int) -> Section:
        return list(filter(lambda item: item.id == id, self.sectionList))[0]

    def getSensorById(self, id: int) -> Sensor:
        return list(filter(lambda item: item.id == id, self.sensorList))[0]

    def getStationById(self, id: int) -> Station:
        return list(filter(lambda item: item.id == id, self.stationList))[0]
    
    def getStationBySectionId(self, sectionId: int) -> Station:
        return self.getSectionById(sectionId).station

    def getTrainById(self, id: int) -> Train:
        return list(filter(lambda item: item.id == id, self.trainList))[0]

    # 指定されたsectionにいる列車を返す。列車がいなければNoneを返す
    def getTrainInSection(self, section: Section) -> Train:
        trains = list(filter(lambda train: train.currentSection.id == section.id, self.trainList))
        if trains != []:
            return trains[0]
        else:
            return None

    # 線路上のある点からある点までの距離を返す
    # 2つの地点が同じsectionに存在する場合、s1>s2だと負の値を返す
    def getDistance(self, s1: Section, mileage1: float, s2: Section, mileage2: float, originalStartSection: Section=None):
        distance = 0
        testSection = s1
        if originalStartSection == None:
            originalStartSection = s1
        while testSection.id != s2.id:
            distance += testSection.length
            if testSection.targetJunction.outSectionCurve == None:
                testSection = testSection.targetJunction.getOutSection()
            else:
                distanceFrom2OutJucntionToS2ViaStraight = self.getDistance(testSection.targetJunction.outSectionStraight, 0, s2, mileage2, originalStartSection)
                distanceFrom2OutJucntionToS2ViaCurve = self.getDistance(testSection.targetJunction.outSectionCurve, 0, s2, mileage2, originalStartSection)
                return distance - mileage1 + min(distanceFrom2OutJucntionToS2ViaStraight, distanceFrom2OutJucntionToS2ViaCurve)
            if testSection.id == originalStartSection.id:
                break  # 1周して戻ってきた場合は終了
        return distance - mileage1 + mileage2
