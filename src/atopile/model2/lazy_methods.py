import functools
import itertools
from collections import defaultdict
from typing import Any, Callable, Hashable, Iterable, Iterator, Optional, TypeVar

import toolz.curried
from toolz import compose, groupby
from toolz.curried import map as _map

from atopile.model2 import datamodel as dm1
from atopile.model2.datatypes import KeyOptItem, Ref
from atopile.model2.flat_datamodel import Instance

T = TypeVar("T")


def filter_values(__function: Callable[[T], bool]) -> Callable[[tuple[Hashable, T]], bool]:
    """Curried function that acts on the values of key-value pairs passed to it."""
    def __value_filter(item: tuple[Hashable, T]) -> bool:
        return __function(item[1])
    return toolz.curried.filter(__value_filter)


def map_values(__function: Callable[[T], Any]) -> Callable[[tuple[Hashable, T]], tuple[Hashable, Any]]:
    """Curried function that maps the values of key-value pairs passed to it."""
    def __value_map(item: tuple[Hashable, T]) -> tuple[Hashable, Any]:
        return (item[0], __function(item[1]))
    return toolz.curried.map(__value_map)


def dfs(instance: Instance) -> Iterator[Instance]:
    """Depth-first search of the instance tree."""
    yield instance

    for child in instance.children.values():
        if isinstance(child, Instance):
            yield from dfs(child)


def dfs_with_ref(instance: Instance, start_ref: Optional[Ref] = None) -> Iterator[KeyOptItem[Ref, Instance]]:
    """Depth-first search of the instance tree."""
    if start_ref is None:
        start_ref = Ref(())

    yield KeyOptItem.from_kv(start_ref, instance)

    for name, child in instance.children.items():
        if isinstance(child, Instance):
            yield from dfs_with_ref(child, start_ref.add_name(name))


def any_supers_match(*supers: dm1.Object) -> Callable[[Instance], bool]:
    """Return a filter which passes if any of the instance's supers match the given supers."""
    allowed_supers_identity_set = set(id(s) for s in supers)

    def _filter(instance: Instance) -> bool:
        for s in instance.origin.supers_bfs:
            if id(s) in allowed_supers_identity_set:
                return True
        return False

    return _filter


# pre-created filters for common types
match_connectables = any_supers_match(dm1.PIN, dm1.SIGNAL, dm1.INTERFACE)
match_pins_and_signals = any_supers_match(dm1.PIN, dm1.SIGNAL)
match_interfaces = any_supers_match(dm1.INTERFACE)
match_components = any_supers_match(dm1.COMPONENT)
match_modules = any_supers_match(dm1.MODULE)


def find_like_instances(iterable: Iterable[Instance], default_keys: Optional[tuple[str]] = None) -> defaultdict[tuple, list[Instance]]:
    """Extract "like" Instances, where "likeness" is qualified by equalities of keys."""
    if default_keys is None:
        default_keys = ("mfn", "value", "footprint")

    def __key(instance: Instance) -> tuple:
        keys = instance.children.get("__keys__", default_keys)
        return tuple(instance.children.get(key_n) for key_n in keys)

    return groupby(__key, iterable)


def joined_to_me(instance: Instance) -> Iterator[Instance]:
    """Iterate over instances that are joined to me."""
    for joint in instance.joined_to_me:
        if joint.source is instance:
            yield joint.target
        else:
            yield joint.source


def iter_nets(root: Instance) -> Iterator[Iterator[Instance]]:
    """Iterate over all the nets in the tree."""
    seen: set[int] = set()

    def _dfs_joins(instance: Instance) -> Iterator[Instance]:
        if id(instance) in seen:
            return

        seen.add(id(instance))

        yield instance

        for other in joined_to_me(instance):
            yield from _dfs_joins(other)

    for connectable in filter(match_connectables, dfs(root)):
        if id(connectable) in seen:
            continue
        yield _dfs_joins(connectable)


def iter_parents(instance: Instance, include_self: bool = True) -> Iterator[Instance]:
    """Iterate over all the parents of an instance."""
    if include_self:
        yield instance
    while instance.parent is not None:
        instance = instance.parent
        yield instance


def closest_common(
    things: Iterable[Iterable[T]],
    __key: Callable[[T], Hashable] = hash,
    validate_common_root: bool = False
) -> T:
    """Returns the closest common item between a set of iterables."""
    if not things:
        raise ValueError("No things given.")

    things = iter(things)

    # make a yardstick of the first iterable
    # this is a dict with the keys being the __key() of the items
    # and the values being the index of the item in the iterable
    index_and_item = itertools.tee(enumerate(next(things)))
    key_to_index_map = dict((__key(item), i) for i, item in index_and_item[0])
    index_to_item_map = dict((i, item) for i, item in index_and_item[1])

    # set the index of the common item
    # this starts at 0 because if there's no other item we
    # just want to return the first item
    common_i = 0
    max_i = len(key_to_index_map) - 1

    def shortcut_if_common_is_already_root():
        if not validate_common_root:
            if common_i == max_i:
                # return early in the case we're already at the root
                return index_to_item_map[common_i]

    shortcut_if_common_is_already_root()

    for thing in things:
        for item in thing:
            key = __key(item)
            if key in key_to_index_map:
                # if the item is in the yardstick, then we've found a common item
                # if the new common item is further than the old common item, we update it
                item_common_i = key_to_index_map[key]
                if item_common_i > common_i:
                    common_i = item_common_i
                    shortcut_if_common_is_already_root()
                break
        else:
            # if we didn't find a common item, then we raise an error
            raise ValueError("No common item found.")

    return index_to_item_map[common_i]


def lowest_common_parent(instances: Iterable[Instance], include_self: bool = True) -> Instance:
    """
    Return the lowest common parent of a set of instances.
    """
    __iter_parents = functools.partial(iter_parents, include_self=include_self)
    return closest_common(map(__iter_parents, instances), __key=id)
