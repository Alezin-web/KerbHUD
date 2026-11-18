"""Layout (ctypes) da memória compartilhada nativa do Le Mans Ultimate (`LMU_Data`).

Fonte do layout: header `SharedMemoryInterface.hpp` / `InternalsPlugin.hpp`
da Studio 397 (distribuído dentro da pasta do jogo em
`Support\\SharedMemoryInterface`), na forma mapeada pelo projeto
pyLMUSharedMemory (licença MIT, https://github.com/TinyPedal/pyLMUSharedMemory).
Transcrito aqui para não depender de pacote externo.

ATENÇÃO: a ORDEM e os TIPOS dos campos definem os offsets. Se uma atualização do
jogo alterar o header, os offsets mudam. Por isso o provider valida o tamanho do
mapeamento e o comando `diag` mostra valores brutos para conferência.
Todas as estruturas usam `#pragma pack(4)`.
"""
from __future__ import annotations

import ctypes as C

MAX_MAPPED_VEHICLES = 104
MAX_PATH_LENGTH = 260
LMU_SHARED_MEMORY_NAME = "LMU_Data"


class _S(C.Structure):
    _pack_ = 4


class Vect3(_S):
    _fields_ = [("x", C.c_double), ("y", C.c_double), ("z", C.c_double)]


class Wheel(_S):
    _fields_ = [
        ("mSuspensionDeflection", C.c_double), ("mRideHeight", C.c_double),
        ("mSuspForce", C.c_double), ("mBrakeTemp", C.c_double),
        ("mBrakePressure", C.c_double), ("mRotation", C.c_double),
        ("mLateralPatchVel", C.c_double), ("mLongitudinalPatchVel", C.c_double),
        ("mLateralGroundVel", C.c_double), ("mLongitudinalGroundVel", C.c_double),
        ("mCamber", C.c_double), ("mLateralForce", C.c_double),
        ("mLongitudinalForce", C.c_double), ("mTireLoad", C.c_double),
        ("mGripFract", C.c_double), ("mPressure", C.c_double),
        ("mTemperature", C.c_double * 3), ("mWear", C.c_double),
        ("mTerrainName", C.c_char * 16), ("mSurfaceType", C.c_ubyte),
        ("mFlat", C.c_bool), ("mDetached", C.c_bool),
        ("mStaticUndeflectedRadius", C.c_ubyte),
        ("mVerticalTireDeflection", C.c_double), ("mWheelYLocation", C.c_double),
        ("mToe", C.c_double), ("mTireCarcassTemperature", C.c_double),
        ("mTireInnerLayerTemperature", C.c_double * 3),
        ("mOptimalTemp", C.c_float), ("mCompoundIndex", C.c_ubyte),
        ("mCompoundType", C.c_ubyte), ("mExpansion", C.c_ubyte * 18),
    ]


class VehicleTelemetry(_S):
    """TelemInfoV01"""

    _fields_ = [
        ("mID", C.c_int), ("mDeltaTime", C.c_double), ("mElapsedTime", C.c_double),
        ("mLapNumber", C.c_int), ("mLapStartET", C.c_double),
        ("mVehicleName", C.c_char * 64), ("mTrackName", C.c_char * 64),
        ("mPos", Vect3), ("mLocalVel", Vect3), ("mLocalAccel", Vect3),
        ("mOri", Vect3 * 3), ("mLocalRot", Vect3), ("mLocalRotAccel", Vect3),
        ("mGear", C.c_int), ("mEngineRPM", C.c_double),
        ("mEngineWaterTemp", C.c_double), ("mEngineOilTemp", C.c_double),
        ("mClutchRPM", C.c_double),
        ("mUnfilteredThrottle", C.c_double), ("mUnfilteredBrake", C.c_double),
        ("mUnfilteredSteering", C.c_double), ("mUnfilteredClutch", C.c_double),
        ("mFilteredThrottle", C.c_double), ("mFilteredBrake", C.c_double),
        ("mFilteredSteering", C.c_double), ("mFilteredClutch", C.c_double),
        ("mSteeringShaftTorque", C.c_double),
        ("mFront3rdDeflection", C.c_double), ("mRear3rdDeflection", C.c_double),
        ("mFrontWingHeight", C.c_double), ("mFrontRideHeight", C.c_double),
        ("mRearRideHeight", C.c_double), ("mDrag", C.c_double),
        ("mFrontDownforce", C.c_double), ("mRearDownforce", C.c_double),
        ("mFuel", C.c_double), ("mEngineMaxRPM", C.c_double),
        ("mScheduledStops", C.c_ubyte), ("mOverheating", C.c_bool),
        ("mDetached", C.c_bool), ("mHeadlights", C.c_bool),
        ("mDentSeverity", C.c_ubyte * 8),
        ("mLastImpactET", C.c_double), ("mLastImpactMagnitude", C.c_double),
        ("mLastImpactPos", Vect3), ("mEngineTorque", C.c_double),
        ("mCurrentSector", C.c_int), ("mSpeedLimiter", C.c_ubyte),
        ("mMaxGears", C.c_ubyte), ("mFrontTireCompoundIndex", C.c_ubyte),
        ("mRearTireCompoundIndex", C.c_ubyte), ("mFuelCapacity", C.c_double),
        ("mFrontFlapActivated", C.c_ubyte), ("mRearFlapActivated", C.c_ubyte),
        ("mRearFlapLegalStatus", C.c_ubyte), ("mIgnitionStarter", C.c_ubyte),
        ("mFrontTireCompoundName", C.c_char * 18),
        ("mRearTireCompoundName", C.c_char * 18),
        ("mSpeedLimiterAvailable", C.c_ubyte), ("mAntiStallActivated", C.c_ubyte),
        ("mUnused", C.c_ubyte * 2),
        ("mVisualSteeringWheelRange", C.c_float), ("mRearBrakeBias", C.c_double),
        ("mTurboBoostPressure", C.c_double),
        ("mPhysicsToGraphicsOffset", C.c_float * 3),
        ("mPhysicalSteeringWheelRange", C.c_float),
        ("mDeltaBest", C.c_double), ("mBatteryChargeFraction", C.c_double),
        ("mElectricBoostMotorTorque", C.c_double), ("mElectricBoostMotorRPM", C.c_double),
        ("mElectricBoostMotorTemperature", C.c_double),
        ("mElectricBoostWaterTemperature", C.c_double),
        ("mElectricBoostMotorState", C.c_ubyte), ("mLapInvalidated", C.c_bool),
        ("mABSActive", C.c_bool), ("mTCActive", C.c_bool),
        ("mSpeedLimiterActive", C.c_bool),
        ("mWiperState", C.c_uint8), ("mTC", C.c_uint8), ("mTCMax", C.c_uint8),
        ("mTCSlip", C.c_uint8), ("mTCSlipMax", C.c_uint8), ("mTCCut", C.c_uint8),
        ("mTCCutMax", C.c_uint8), ("mABS", C.c_uint8), ("mABSMax", C.c_uint8),
        ("mMotorMap", C.c_uint8), ("mMotorMapMax", C.c_uint8),
        ("mMigration", C.c_uint8), ("mMigrationMax", C.c_uint8),
        ("mFrontAntiSway", C.c_uint8), ("mFrontAntiSwayMax", C.c_uint8),
        ("mRearAntiSway", C.c_uint8), ("mRearAntiSwayMax", C.c_uint8),
        ("mLiftAndCoastProgress", C.c_uint8), ("mTrackLimitsSteps", C.c_uint8),
        ("mRegen", C.c_float), ("mStateOfCharge", C.c_float),
        ("mVirtualEnergy", C.c_float),
        ("mTimeGapCarAhead", C.c_float), ("mTimeGapCarBehind", C.c_float),
        ("mTimeGapPlaceAhead", C.c_float), ("mTimeGapPlaceBehind", C.c_float),
        ("mVehicleModel", C.c_char * 30), ("mVehicleClass", C.c_uint8),
        ("mVehicleChampionship", C.c_uint8), ("mExpansion", C.c_ubyte * 20),
        ("mWheels", Wheel * 4),
    ]


class VehicleScoring(_S):
    """VehicleScoringInfoV01"""

    _fields_ = [
        ("mID", C.c_int), ("mDriverName", C.c_char * 32),
        ("mVehicleName", C.c_char * 64), ("mTotalLaps", C.c_short),
        ("mSector", C.c_byte), ("mFinishStatus", C.c_byte),
        ("mLapDist", C.c_double), ("mPathLateral", C.c_double),
        ("mTrackEdge", C.c_double),
        ("mBestSector1", C.c_double), ("mBestSector2", C.c_double),
        ("mBestLapTime", C.c_double),
        ("mLastSector1", C.c_double), ("mLastSector2", C.c_double),
        ("mLastLapTime", C.c_double),
        ("mCurSector1", C.c_double), ("mCurSector2", C.c_double),
        ("mNumPitstops", C.c_short), ("mNumPenalties", C.c_short),
        ("mIsPlayer", C.c_bool), ("mControl", C.c_byte), ("mInPits", C.c_bool),
        ("mPlace", C.c_ubyte), ("mVehicleClass", C.c_char * 32),
        ("mTimeBehindNext", C.c_double), ("mLapsBehindNext", C.c_int),
        ("mTimeBehindLeader", C.c_double), ("mLapsBehindLeader", C.c_int),
        ("mLapStartET", C.c_double),
        ("mPos", Vect3), ("mLocalVel", Vect3), ("mLocalAccel", Vect3),
        ("mOri", Vect3 * 3), ("mLocalRot", Vect3), ("mLocalRotAccel", Vect3),
        ("mHeadlights", C.c_ubyte), ("mPitState", C.c_ubyte),
        ("mServerScored", C.c_ubyte), ("mIndividualPhase", C.c_ubyte),
        ("mQualification", C.c_int), ("mTimeIntoLap", C.c_double),
        ("mEstimatedLapTime", C.c_double), ("mPitGroup", C.c_char * 24),
        ("mFlag", C.c_ubyte), ("mUnderYellow", C.c_bool),
        ("mCountLapFlag", C.c_ubyte), ("mInGarageStall", C.c_bool),
        ("mUpgradePack", C.c_ubyte * 16), ("mPitLapDist", C.c_float),
        ("mBestLapSector1", C.c_float), ("mBestLapSector2", C.c_float),
        ("mSteamID", C.c_ulonglong), ("mVehFilename", C.c_char * 32),
        ("mAttackMode", C.c_short), ("mFuelFraction", C.c_ubyte),
        ("mDRSState", C.c_bool), ("mExpansion", C.c_ubyte * 4),
    ]


class ScoringInfo(_S):
    """ScoringInfoV01"""

    _fields_ = [
        ("mTrackName", C.c_char * 64), ("mSession", C.c_int),
        ("mCurrentET", C.c_double), ("mEndET", C.c_double),
        ("mMaxLaps", C.c_int), ("mLapDist", C.c_double),
        ("mResultsStreamPointer", C.c_ubyte * 8), ("mNumVehicles", C.c_int),
        ("mGamePhase", C.c_ubyte), ("mYellowFlagState", C.c_char),
        ("mSectorFlag", C.c_ubyte * 3), ("mStartLight", C.c_ubyte),
        ("mNumRedLights", C.c_ubyte), ("mInRealtime", C.c_bool),
        ("mPlayerName", C.c_char * 32), ("mPlrFileName", C.c_char * 64),
        ("mDarkCloud", C.c_double), ("mRaining", C.c_double),
        ("mAmbientTemp", C.c_double), ("mTrackTemp", C.c_double),
        ("mWind", Vect3), ("mMinPathWetness", C.c_double),
        ("mMaxPathWetness", C.c_double), ("mGameMode", C.c_ubyte),
        ("mIsPasswordProtected", C.c_bool), ("mServerPort", C.c_ushort),
        ("mServerPublicIP", C.c_uint), ("mMaxPlayers", C.c_int),
        ("mServerName", C.c_char * 32), ("mStartET", C.c_float),
        ("mAvgPathWetness", C.c_double), ("mSessionTimeRemaining", C.c_float),
        ("mTimeOfDay", C.c_float), ("mIsFixedSetup", C.c_bool),
        ("mTrackGripLevel", C.c_uint8), ("mCloudCoverage", C.c_uint8),
        ("mTrackLimitsStepsPerPenalty", C.c_uint8),
        ("mTrackLimitsStepsPerPoint", C.c_uint8),
        ("mExpansion", C.c_ubyte * 187), ("mVehiclePointer", C.c_ubyte * 8),
    ]


class ApplicationState(_S):
    _fields_ = [
        ("mAppWindow", C.c_ulonglong), ("mWidth", C.c_uint), ("mHeight", C.c_uint),
        ("mRefreshRate", C.c_uint), ("mWindowed", C.c_uint),
        ("mOptionsLocation", C.c_ubyte), ("mOptionsPage", C.c_char * 31),
        ("mExpansion", C.c_ubyte * 204),
    ]


class ScoringData(_S):
    _fields_ = [
        ("scoringInfo", ScoringInfo),
        ("scoringStreamSize", C.c_ubyte * 12),
        ("vehScoringInfo", VehicleScoring * MAX_MAPPED_VEHICLES),
        ("scoringStream", C.c_char * 65536),
    ]


class TelemetryData(_S):
    _fields_ = [
        ("activeVehicles", C.c_uint8), ("playerVehicleIdx", C.c_uint8),
        ("playerHasVehicle", C.c_bool),
        ("telemInfo", VehicleTelemetry * MAX_MAPPED_VEHICLES),
    ]


class PathData(_S):
    _fields_ = [
        ("userData", C.c_char * MAX_PATH_LENGTH),
        ("customVariables", C.c_char * MAX_PATH_LENGTH),
        ("stewardResults", C.c_char * MAX_PATH_LENGTH),
        ("playerProfile", C.c_char * MAX_PATH_LENGTH),
        ("pluginsFolder", C.c_char * MAX_PATH_LENGTH),
    ]


class Event(_S):
    """Enum SharedMemoryEvent reescrita como struct (16 × uint32)."""

    _fields_ = [(n, C.c_uint) for n in (
        "SME_ENTER", "SME_EXIT", "SME_STARTUP", "SME_SHUTDOWN", "SME_LOAD",
        "SME_UNLOAD", "SME_START_SESSION", "SME_END_SESSION", "SME_ENTER_REALTIME",
        "SME_EXIT_REALTIME", "SME_UPDATE_SCORING", "SME_UPDATE_TELEMETRY",
        "SME_INIT_APPLICATION", "SME_UNINIT_APPLICATION", "SME_SET_ENVIRONMENT",
        "SME_FFB",
    )]


class Generic(_S):
    _fields_ = [
        ("events", Event), ("gameVersion", C.c_int), ("FFBTorque", C.c_float),
        ("appInfo", ApplicationState),
    ]


class ObjectOut(_S):
    _fields_ = [
        ("generic", Generic), ("paths", PathData),
        ("scoring", ScoringData), ("telemetry", TelemetryData),
    ]


# Offsets (bytes) usados pelo provider para ler só o necessário.
OFF_GENERIC = ObjectOut.generic.offset
OFF_PATHS = ObjectOut.paths.offset
OFF_SCORING_INFO = ObjectOut.scoring.offset + ScoringData.scoringInfo.offset
OFF_SCORING_VEHICLES = ObjectOut.scoring.offset + ScoringData.vehScoringInfo.offset
OFF_TELEM_HEADER = ObjectOut.telemetry.offset
OFF_TELEM_VEHICLES = ObjectOut.telemetry.offset + TelemetryData.telemInfo.offset
SIZE_TOTAL = C.sizeof(ObjectOut)
