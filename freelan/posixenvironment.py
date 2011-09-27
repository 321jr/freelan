"""A POSIX based system specialized environment class."""

from base_environment import BaseEnvironment

import os
import platform

import SCons

import tools

class PosixEnvironment(BaseEnvironment):
    """An environment class."""

    def __init__(
        self,
        _platform=None,
        _tools=None,
        toolpath=None,
        variables=None,
        parse_flags=None,
        **kw
    ):
        """Create a new PosixEnvironment instance."""

        BaseEnvironment.__init__(
            self,
            _platform,
            _tools,
            toolpath,
            variables,
            parse_flags,
            **kw
        )

        self['CXXFLAGS'].append('-Wall')
        self['CXXFLAGS'].append('-Wextra')
        self['CXXFLAGS'].append('-Werror')
        self['CXXFLAGS'].append('-pedantic')
        self['CXXFLAGS'].append('-Wshadow')
        self['CXXFLAGS'].append('-Wno-long-long')
        self['CXXFLAGS'].append('-Wno-uninitialized')

        if self.arch != platform.machine():
            if tools.is_32_bits_architecture(self.arch):
                self['CXXFLAGS'].append('-m32')
                self['LINKFLAGS'].append('-m32')
            elif tools.is_64_bits_architecture(self.arch):
                self['CXXFLAGS'].append('-m64')
                self['LINKFLAGS'].append('-m64')

        self['ARGUMENTS'].setdefault('prefix', '/usr/local')

    def FreelanLibrary(self, target_dir, name, major, minor, include_path, source_files, libraries):
        """Build a library."""

        env = {
            'CPPPATH': [include_path],
            'SHLINKFLAGS': ['-Wl,-soname,lib%s.so.%s' % (name, major)],
            'LIBS': libraries
        }

        # We add values to existing ones
        for key, value in env.items():
            if isinstance(value, list):
                if key in self:
                    env[key] += self[key]

        shared_library = self.SharedLibrary(os.path.join(target_dir, name), source_files, **env)
        static_library = self.StaticLibrary(os.path.join(target_dir, name + '_static'), source_files, **env)
        versioned_shared_library = self.Command(os.path.join(target_dir, 'lib%s.so.%s.%s' % (name, major, minor)), shared_library, SCons.Script.Copy("$TARGET", "$SOURCE"))

        return shared_library + static_library + versioned_shared_library
