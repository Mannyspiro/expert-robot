"""Reversible private records for three ordered volumetric Go-like boards.

This is a bounded recording/encoding adapter, not a cipher or a complete Go
engine. Move checks establish occupancy/capture-record consistency only, not
liberties, suicide, turn order, Ko legality, scoring or cryptographic entropy.
Generic higher-dimensional grids do not implement E8, Leech, p-adic or Clifford
mathematics. Boards/permutations/Ko/history never enter a key, KDF or public AAD.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import math
import struct
from functools import wraps

from .titan_protocol_model import canonical_json_bytes

BOARD_COUNT = 3
MAX_POINTS_PER_BOARD = 32768
MAX_MOVES = 1024
MAX_PAYLOAD_BYTES = 1048568
HANDOFF_SHAPE = (7, 7, 7)
OPERATIONAL_SHAPE = (19, 19, 19)
OCTOBER_PROFILE = "titan-oct25-three7-state3/1"
NOVEMBER_PROFILE = "titan-nov05-three19-mirror/1"
GENERIC_PROFILE = "titan-cartesian-recording/1"
HANDOFF_OFFSETS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
                   (1, 1, 0), (-1, -1, 0), (1, -1, 0), (-1, 1, 0), (0, 1, 1), (0, -1, -1))


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("bounded integer required")
    return value


def _shape(value):
    if type(value) is not tuple or not 3 <= len(value) <= 8:
        raise ValueError("3..8 declared Cartesian axes required")
    for size in value:
        _integer(size, 2, 19)
    if math.prod(value) > MAX_POINTS_PER_BOARD:
        raise ValueError("board point ceiling exceeded")
    return value


@dataclass(frozen=True)
class BoardGeometry:
    shape: tuple[int, ...]
    offsets: tuple[tuple[int, ...], ...]
    wrapped: bool = True
    stencil_id: str = "explicit-grid-offsets/1"

    def __post_init__(self):
        _shape(self.shape)
        if (type(self.wrapped) is not bool or not isinstance(self.stencil_id, str)
                or not self.stencil_id.strip() or len(self.stencil_id) > 120
                or type(self.offsets) is not tuple or not 1 <= len(self.offsets) <= 128):
            raise ValueError("explicit bounded geometry/stencil required")
        for offset in self.offsets:
            if type(offset) is not tuple or len(offset) != len(self.shape) or not any(offset):
                raise ValueError("nonzero offset with exact axis count required")
            for value in offset:
                _integer(value, -1, 1)
        if len(set(self.offsets)) != len(self.offsets):
            raise ValueError("duplicate stencil direction")


@dataclass(frozen=True)
class BoardMove:
    board: int
    color: int
    coordinate: tuple[int, ...] | None
    captured: tuple[tuple[int, ...], ...] = ()


@dataclass(frozen=True)
class BoardRecord:
    """Initial storage-order cells, logical-coordinate events and current Ko FIFO.

    Ko is a preserved snapshot. Its relationship to omitted/pre-record history
    is not asserted; advance_ko exposes the documented arithmetic separately.
    """
    geometry: BoardGeometry
    initial_boards: tuple[bytes, ...]
    permutations: tuple[tuple[int, ...], ...]
    moves: tuple[BoardMove, ...] = ()
    ko_register: tuple[int, ...] = (0,) * 16
    profile: str = GENERIC_PROFILE


def coordinate_index(coordinate, shape):
    """Axis zero is fastest: x+s*y+s²*z for a cubic 3D board."""
    _shape(shape)
    if type(coordinate) is not tuple or len(coordinate) != len(shape):
        raise ValueError("coordinate axis count mismatch")
    result = 0; stride = 1
    for value, size in zip(coordinate, shape):
        result += _integer(value, 0, size - 1) * stride
        stride *= size
    return result


def index_coordinate(index, shape):
    _shape(shape); _integer(index, 0, math.prod(shape) - 1)
    result = []
    for size in shape:
        result.append(index % size); index //= size
    return tuple(result)


def neighbor_indices(geometry, coordinate):
    """One destination per ordered stencil direction, retaining wrap collisions."""
    if not isinstance(geometry, BoardGeometry):
        raise ValueError("typed geometry required")
    coordinate_index(coordinate, geometry.shape)
    result = []
    for offset in geometry.offsets:
        target = tuple(value + delta for value, delta in zip(coordinate, offset))
        if geometry.wrapped:
            target = tuple(value % size for value, size in zip(target, geometry.shape))
        elif any(value < 0 or value >= size for value, size in zip(target, geometry.shape)):
            continue
        result.append(coordinate_index(target, geometry.shape))
    return tuple(result)


def empty_board_record(geometry, *, profile=GENERIC_PROFILE):
    if not isinstance(geometry, BoardGeometry):
        raise ValueError("typed geometry required")
    count = math.prod(geometry.shape)
    return BoardRecord(geometry, (bytes(count),) * BOARD_COUNT, (tuple(range(count)),) * BOARD_COUNT, profile=profile)


def handoff_geometry():
    """The documented7³ wrapped12-direction grid; not E8/Leech geometry."""
    return BoardGeometry(HANDOFF_SHAPE, HANDOFF_OFFSETS, True, "handoff-20261025-toroidal12/1")


def handoff_board_record():
    return empty_board_record(handoff_geometry(), profile=OCTOBER_PROFILE)


def operational_board_record():
    """Nov19³/four-state recording profile, with an explicitly declared stencil.

    The supplied factory carries the Oct twelve offsets onto a19³ domain. This
    is a recording choice, not a claim that all later topology proposals use it.
    Mirror3 is immutable under the supported placement/capture record checks;
    mirror physics, coupling, reflections and rotors are not implemented.
    """
    geometry = BoardGeometry(OPERATIONAL_SHAPE, HANDOFF_OFFSETS, True, "oct25-toroidal12-on-nov19-recording/1")
    return empty_board_record(geometry, profile=NOVEMBER_PROFILE)


def synthetic_board_example():
    """Deterministic public fixture; its permutations are not encryption keys."""
    record = operational_board_record(); count = math.prod(record.geometry.shape)
    permutations = tuple(tuple((factor * index + shift) % count for index in range(count))
                         for factor, shift in ((5, 17), (7, 113), (11, 997)))
    boards = [bytearray(board) for board in record.initial_boards]
    mirror = coordinate_index((1, 2, 3), record.geometry.shape)
    boards[0][permutations[0][mirror]] = 3
    moves = (BoardMove(0, 1, (0, 0, 0)), BoardMove(1, 2, None), BoardMove(2, 2, (18, 18, 18)))
    ko = advance_ko(record.ko_register, permutations[0][0], 0)
    ko = advance_ko(ko, permutations[2][-1], 0)
    return BoardRecord(record.geometry, tuple(bytes(board) for board in boards), permutations, moves, ko, NOVEMBER_PROFILE)


def advance_ko(register, mapped_node, cleared_neighbors):
    """Documented uint8 FIFO bookkeeping only; no Go legality/entropy proof."""
    if type(register) is not tuple or len(register) != 16:
        raise ValueError("sixteen-entry Ko FIFO required")
    for entry in register:
        _integer(entry, 0, 255)
    _integer(mapped_node, 0, MAX_POINTS_PER_BOARD - 1)
    _integer(cleared_neighbors, 0, 128)
    return register[1:] + ((mapped_node + cleared_neighbors) % 256,)


def replay_board_record(record):
    """Validate a record and reproduce final cells, without claiming Go legality."""
    if not isinstance(record, BoardRecord) or not isinstance(record.geometry, BoardGeometry):
        raise ValueError("typed board record required")
    count = math.prod(record.geometry.shape)
    if type(record.profile) is not str or record.profile not in {OCTOBER_PROFILE, NOVEMBER_PROFILE, GENERIC_PROFILE}:
        raise ValueError("unsupported recording profile")
    if record.profile == OCTOBER_PROFILE and record.geometry != handoff_geometry():
        raise ValueError("October profile requires the documented7³ wrapped twelve-offset geometry")
    if record.profile == NOVEMBER_PROFILE and record.geometry.shape != OPERATIONAL_SHAPE:
        raise ValueError("November profile requires three19³ boards")
    maximum_cell = 3 if record.profile == NOVEMBER_PROFILE else 2
    if (type(record.initial_boards) is not tuple or len(record.initial_boards) != BOARD_COUNT
            or type(record.permutations) is not tuple or len(record.permutations) != BOARD_COUNT
            or type(record.moves) is not tuple or len(record.moves) > MAX_MOVES
            or type(record.ko_register) is not tuple or len(record.ko_register) != 16):
        raise ValueError("exact three-board record and bounded history/Ko required")
    for board, permutation in zip(record.initial_boards, record.permutations):
        if type(board) is not bytes or len(board) != count or any(value > maximum_cell for value in board):
            raise ValueError("board cell value outside declared recording profile")
        if (type(permutation) is not tuple or len(permutation) != count
                or any(type(index) is not int for index in permutation) or set(permutation) != set(range(count))):
            raise ValueError("each logical-to-storage permutation must be a complete bijection")
    for token in record.ko_register:
        _integer(token, 0, 255)
    boards = [bytearray(board) for board in record.initial_boards]
    for move in record.moves:
        if not isinstance(move, BoardMove):
            raise ValueError("typed move required")
        board_id = _integer(move.board, 0, BOARD_COUNT - 1); _integer(move.color, 1, 2)
        if type(move.captured) is not tuple or len(move.captured) > 64:
            raise ValueError("bounded explicit capture record required")
        if move.coordinate is None:
            if move.captured:
                raise ValueError("a recorded pass cannot remove cells")
            continue
        logical = coordinate_index(move.coordinate, record.geometry.shape)
        storage = record.permutations[board_id][logical]
        if boards[board_id][storage] != 0:
            raise ValueError("recorded placement must target an empty cell")
        captures = [record.permutations[board_id][coordinate_index(point, record.geometry.shape)] for point in move.captured]
        if len(set(captures)) != len(captures) or any(boards[board_id][point] != 3 - move.color for point in captures):
            raise ValueError("recorded captures must name distinct opponent cells")
        boards[board_id][storage] = move.color
        for point in captures:
            boards[board_id][point] = 0
    return tuple(bytes(board) for board in boards)


def _b64(raw):
    return base64.b64encode(raw).decode("ascii")


def _unb64(value):
    if type(value) is not str:
        raise ValueError("base64 text required")
    raw = base64.b64decode(value, validate=True)
    if _b64(raw) != value:
        raise ValueError("canonical base64 required")
    return raw


def _mapping(record):
    final = replay_board_record(record)
    return {"schema": "titan-three-board-record/1", "board_count": BOARD_COUNT, "profile": record.profile,
        "geometry": {"shape": list(record.geometry.shape), "offsets": [list(value) for value in record.geometry.offsets],
                     "wrapped": record.geometry.wrapped, "stencil_id": record.geometry.stencil_id},
        "indexing": "axis0-fast-mixed-radix", "permutation_direction": "logical_to_storage",
        "initial_boards_b64": [_b64(value) for value in record.initial_boards],
        "permutations_u32le_b64": [_b64(b"".join(struct.pack("<I", value) for value in permutation)) for permutation in record.permutations],
        "moves": [{"board": move.board, "color": move.color, "coordinate": list(move.coordinate) if move.coordinate is not None else None,
                   "captured": [list(value) for value in move.captured]} for move in record.moves],
        "ko_register": list(record.ko_register),
        "ko_validation": "uint8_fifo_snapshot;history_relation_not_verified",
        "final_boards_b64": [_b64(value) for value in final],
        "validation_scope": "record_consistency_not_go_legality_or_crypto_security",
        "qualification": False, "promotion_authority": False}


def _record(value):
    fields = {"schema", "board_count", "profile", "geometry", "indexing", "permutation_direction", "initial_boards_b64",
              "permutations_u32le_b64", "moves", "ko_register", "ko_validation", "final_boards_b64", "validation_scope",
              "qualification", "promotion_authority"}
    if type(value) is not dict or set(value) != fields or value["schema"] != "titan-three-board-record/1":
        raise ValueError("exact versioned board record required")
    geometry = value["geometry"]
    if type(geometry) is not dict or set(geometry) != {"shape", "offsets", "wrapped", "stencil_id"}:
        raise ValueError("exact geometry fields required")
    for name in ("initial_boards_b64", "permutations_u32le_b64", "final_boards_b64"):
        if type(value[name]) is not list or len(value[name]) != BOARD_COUNT:
            raise ValueError("exact three-board field required")
    if type(value["moves"]) is not list or len(value["moves"]) > MAX_MOVES:
        raise ValueError("move count ceiling exceeded")
    if type(value["ko_register"]) is not list or len(value["ko_register"]) != 16:
        raise ValueError("exact Ko FIFO required")
    typed_geometry = BoardGeometry(tuple(geometry["shape"]), tuple(tuple(offset) for offset in geometry["offsets"]),
                                   geometry["wrapped"], geometry["stencil_id"])
    count = math.prod(typed_geometry.shape); permutations = []
    for encoded in value["permutations_u32le_b64"]:
        raw = _unb64(encoded)
        if len(raw) != count * 4:
            raise ValueError("permutation byte count mismatch")
        permutations.append(tuple(item[0] for item in struct.iter_unpack("<I", raw)))
    moves = []
    for move in value["moves"]:
        if type(move) is not dict or set(move) != {"board", "color", "coordinate", "captured"}:
            raise ValueError("exact recorded move fields required")
        moves.append(BoardMove(move["board"], move["color"], tuple(move["coordinate"]) if move["coordinate"] is not None else None,
                               tuple(tuple(point) for point in move["captured"])))
    record = BoardRecord(typed_geometry, tuple(_unb64(raw) for raw in value["initial_boards_b64"]),
                         tuple(permutations), tuple(moves), tuple(value["ko_register"]), value["profile"])
    if canonical_json_bytes(_mapping(record)) != canonical_json_bytes(value):
        raise ValueError("record fields/final board differ from validated replay")
    return record


def _parse(raw):
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_PAYLOAD_BYTES:
        raise ValueError("bounded immutable payload bytes required")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError("duplicate JSON field")
            result[key] = value
        return result
    def invalid(_): raise ValueError("nonfinite JSON value")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)
    if canonical_json_bytes(value) != raw:
        raise ValueError("exact canonical payload encoding required")
    return value


def _decode_boundary(call):
    @wraps(call)
    def decoded(*args, **kwargs):
        try:
            return call(*args, **kwargs)
        except (KeyError, TypeError, OverflowError, UnicodeError, RecursionError, struct.error) as exc:
            raise ValueError("invalid private board encoding") from exc
    return decoded


def encode_board_record(record):
    raw = canonical_json_bytes(_mapping(record))
    if len(raw) > MAX_PAYLOAD_BYTES: raise ValueError("board payload byte ceiling exceeded")
    return raw


@_decode_boundary
def decode_board_record(raw):
    return _record(_parse(raw))


def encode_private_board_message(message, record):
    """Plaintext serialization only; encrypt these bytes with a reviewed envelope."""
    if type(message) is not bytes or len(message) > MAX_PAYLOAD_BYTES:
        raise ValueError("bounded original message bytes required")
    raw = canonical_json_bytes({"schema": "titan-private-board-message/1", "message_b64": _b64(message), "board": _mapping(record)})
    if len(raw) > MAX_PAYLOAD_BYTES: raise ValueError("combined private payload byte ceiling exceeded")
    return raw


@_decode_boundary
def decode_private_board_message(raw):
    value = _parse(raw)
    if type(value) is not dict or set(value) != {"schema", "message_b64", "board"} or value["schema"] != "titan-private-board-message/1":
        raise ValueError("exact private message/board payload required")
    return _unb64(value["message_b64"]), _record(value["board"])


def public_board_context():
    """No record argument: public metadata cannot expose board parameters/digests."""
    return {"purpose": "titan-private-payload", "schema": "titan-private-payload/1"}
